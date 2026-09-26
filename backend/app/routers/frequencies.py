"""周波数管理・開局・予約・停波ライフサイクル API。

76.0〜88.9MHz（0.1MHz刻み）の各スロット状態
（EMPTY / RESERVED / LIVE / OFF AIR）を管理する。
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bands import (
    all_frequencies,
    band_of,
    bands_payload,
    validate_free_frequency,
    validate_range,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_user
from app.models.models import (
    BotStation,
    Message,
    Program,
    Reservation,
    Station,
    StationFavorite,
    User,
)
from app.services.sessions import close_session, open_session
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api", tags=["frequencies"])

# 状態の意味:
#   empty    … 完全空きスロット
#   reserved … 予約済み / 開局準備中（RESERVED）
#   live     … 放送中（ON AIR）
#   off_air  … 停波中（OFF AIR）


def _now() -> datetime:
    return datetime.now()


def _all_frequencies() -> list[float]:
    """76.0〜88.9MHz の全スロットを返す（総数は帯域分けで増減しない）。"""
    return all_frequencies()


def _validate_freq(frequency: float) -> float:
    return validate_range(frequency)


async def broadcast_frequency_status(
    frequency: float, status: str, station_id: Optional[int] = None
) -> None:
    """周波数スロットの状態変化を全クライアントへ同期する。"""
    await manager.broadcast_all(
        {
            "type": "frequency_status",
            "frequency": round(frequency, 1),
            "status": status,
            "station_id": station_id,
        }
    )


class ReserveIn(BaseModel):
    callsign: Optional[str] = None
    note: Optional[str] = ""
    start_time: datetime
    end_time: datetime


@router.get("/bands")
async def list_bands():
    """周波数帯の区分（専用局帯 / 自由な周波数）と切り忘れ対策の設定。

    総スロット数は変えずに帯域を分けている（専用局＝24時間常設の申請先）。
    """
    return {"success": True, **bands_payload()}


@router.get("/frequencies")
async def list_frequencies(db: AsyncSession = Depends(get_db)):
    """全スロットの状態一覧（EMPTY / RESERVED / LIVE / OFF AIR）。"""
    now = _now()
    stations = (await db.execute(select(Station))).scalars().all()
    by_freq = {round(s.frequency, 1): s for s in stations}

    reservations = (
        await db.execute(
            select(Reservation).where(
                Reservation.status == "active", Reservation.end_time > now
            )
        )
    ).scalars().all()
    res_by_freq: dict[float, list[Reservation]] = {}
    for r in reservations:
        res_by_freq.setdefault(round(r.frequency, 1), []).append(r)

    slots = []
    for f in _all_frequencies():
        station = by_freq.get(f)
        rs = res_by_freq.get(f, [])
        if station is not None:
            slots.append(
                {
                    "frequency": f,
                    "band": band_of(f),
                    "status": station.status,
                    "station_id": station.id,
                    "callsign": station.callsign,
                    "owner_username": station.owner.username if station.owner else None,
                    "listener_count": manager.channel_count(station.id),
                    "is_dedicated": bool(station.is_dedicated),
                    "reservation": None,
                }
            )
        elif rs:
            r = rs[0]
            slots.append(
                {
                    "frequency": f,
                    "band": band_of(f),
                    "status": "reserved",
                    "station_id": None,
                    "callsign": r.callsign or "予約枠",
                    "owner_username": r.user.username if r.user else None,
                    "listener_count": 0,
                    "is_dedicated": False,
                    "reservation": r.to_dict(),
                }
            )
        else:
            slots.append(
                {
                    "frequency": f,
                    "band": band_of(f),
                    "status": "empty",
                    "station_id": None,
                    "callsign": None,
                    "owner_username": None,
                    "listener_count": 0,
                    "is_dedicated": False,
                    "reservation": None,
                }
            )

    counts = {"empty": 0, "reserved": 0, "live": 0, "off_air": 0}
    for s in slots:
        counts[s["status"]] = counts.get(s["status"], 0) + 1

    info = bands_payload()
    return {
        "success": True,
        "min": settings.station_freq_min,
        "max": settings.station_freq_max,
        "count": len(slots),
        "counts": counts,
        "bands": info["bands"],
        "auto_off": info["auto_off"],
        "slots": slots,
    }


@router.get("/frequencies/{frequency}")
async def get_frequency(frequency: float, db: AsyncSession = Depends(get_db)):
    """単一スロットの状態。"""
    f = _validate_freq(frequency)
    band = band_of(f)
    station = (
        await db.execute(select(Station).where(Station.frequency == f))
    ).scalars().first()
    if station is not None:
        return {
            "success": True,
            "frequency": f,
            "band": band,
            "status": station.status,
            "station": station.to_dict(),
            "reservation": None,
        }
    now = _now()
    r = (
        await db.execute(
            select(Reservation)
            .where(
                Reservation.frequency == f,
                Reservation.status == "active",
                Reservation.end_time > now,
            )
            .order_by(Reservation.start_time.asc())
        )
    ).scalars().first()
    return {
        "success": True,
        "frequency": f,
        "band": band,
        "status": "reserved" if r else "empty",
        "station": None,
        "reservation": r.to_dict() if r else None,
    }


# ---- 時間枠予約 ----

async def _do_reserve(
    frequency: float,
    callsign: Optional[str],
    note: Optional[str],
    start_time: datetime,
    end_time: datetime,
    user: User,
    db: AsyncSession,
) -> Reservation:
    # 時間枠予約は「自由な周波数」（専用局帯以外）のみ
    f = validate_free_frequency(frequency)
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="終了時刻は開始時刻より後を指定してください")

    station = (
        await db.execute(select(Station).where(Station.frequency == f))
    ).scalars().first()
    if station is not None:
        raise HTTPException(status_code=409, detail="この周波数は既に開局されています")

    overlap = (
        await db.execute(
            select(Reservation).where(
                Reservation.frequency == f,
                Reservation.status == "active",
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
        )
    ).scalars().first()
    if overlap is not None:
        raise HTTPException(status_code=409, detail="この時間帯は既に予約されています")

    reservation = Reservation(
        user_id=user.id,
        frequency=f,
        callsign=(callsign or f"{user.username} の予約枠").strip(),
        note=note or "",
        start_time=start_time,
        end_time=end_time,
        status="active",
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)
    await broadcast_frequency_status(f, "reserved", None)
    return reservation


@router.post("/frequencies/{frequency}/reserve", status_code=201)
async def reserve_frequency(
    frequency: float,
    data: ReserveIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """周波数の時間枠を予約する（排他制御：重複時間は409）。"""
    reservation = await _do_reserve(
        frequency, data.callsign, data.note, data.start_time, data.end_time, user, db
    )
    return {"success": True, "reservation": reservation.to_dict()}


class ReserveByBody(BaseModel):
    frequency: float
    callsign: Optional[str] = None
    note: Optional[str] = ""
    start_time: datetime
    end_time: datetime


@router.post("/frequencies/reserve", status_code=201)
async def reserve_frequency_body(
    data: ReserveByBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """周波数予約（POST /api/frequencies/reserve）— 仕様書のパス。"""
    reservation = await _do_reserve(
        data.frequency, data.callsign, data.note, data.start_time, data.end_time, user, db
    )
    return {"success": True, "reservation": reservation.to_dict()}


@router.get("/reservations/mine")
async def my_reservations(
    user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.start_time.asc())
    )
    return {"success": True, "reservations": [r.to_dict() for r in result.scalars().all()]}


@router.delete("/reservations/{reservation_id}")
async def cancel_reservation(
    reservation_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    reservation = await db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="予約が見つかりません")
    if reservation.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="予約をキャンセルする権限がありません")
    reservation.status = "cancelled"
    await db.commit()
    await broadcast_frequency_status(reservation.frequency, "empty", None)
    return {"success": True}


# ---- 放送ライフサイクル（ON AIR / OFF AIR / 廃局）----

def _require_owner(station: Optional[Station], user: User) -> Station:
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="このステーションの権限がありません")
    return station


@router.post("/stations/{station_id}/on-air")
async def station_on_air(
    station_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """放送開始（ON AIR）。放送セッションを自動発行する。"""
    station = _require_owner(await db.get(Station, station_id), user)
    station.set_status("live")
    await db.commit()
    # 予約の有無を問わず、ON AIR した瞬間に放送セッションを自動記録
    session = await open_session(db, station)
    await broadcast_frequency_status(station.frequency, "live", station.id)
    await manager.broadcast(station_id, {"type": "live_update", "is_live": True, "status": "live"})
    return {"success": True, "status": "live", "session_id": session.id}


@router.post("/stations/{station_id}/off-air")
async def station_off_air(
    station_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """停波（OFF AIR）。砂嵐・告知画面へ。放送セッションを自動クローズする。"""
    station = _require_owner(await db.get(Station, station_id), user)
    station.set_status("off_air")
    await db.commit()
    session = await close_session(db, station_id)
    await broadcast_frequency_status(station.frequency, "off_air", station.id)
    await manager.broadcast(station_id, {"type": "live_update", "is_live": False, "status": "off_air"})
    return {"success": True, "status": "off_air", "session_id": session.id if session else None}


@router.delete("/stations/{station_id}")
async def close_station(
    station_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """廃局（周波数返還）。周波数スロットは EMPTY に戻る。"""
    station = _require_owner(await db.get(Station, station_id), user)
    freq = station.frequency
    await db.execute(sa_delete(Message).where(Message.station_id == station_id))
    await db.execute(sa_delete(Program).where(Program.station_id == station_id))
    await db.execute(
        sa_delete(StationFavorite).where(StationFavorite.station_id == station_id)
    )
    # 自動DJ局の設定も削除
    await db.execute(sa_delete(BotStation).where(BotStation.station_id == station_id))
    await db.delete(station)
    await db.commit()
    await broadcast_frequency_status(freq, "empty", None)
    return {"success": True, "frequency": freq}
