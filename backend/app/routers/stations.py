"""ステーション（放送局）API：一覧 / 空き周波数 / 開局 / 管理 / お気に入り / プレビュー。"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bands import (
    bands_payload,
    dedicated_frequencies,
    free_frequencies,
    validate_free_frequency,
)
from app.core.database import get_db
from app.core.security import require_user
from app.core.utils import parse_youtube_id
from app.models.models import (
    BotStation,
    BroadcastSession,
    Message,
    Program,
    Reservation,
    SessionTrack,
    Station,
    StationFavorite,
    User,
)
from app.routers.frequencies import broadcast_frequency_status
from app.services.bot_dj import play_next
from app.services.dj_announce import schedule_track_change
from app.services.sessions import clear_now_playing, close_session, open_session, record_track
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api", tags=["stations"])


def _with_listeners(station: Station, bot_ids: Optional[set] = None) -> dict:
    data = station.to_dict()
    data["listener_count"] = manager.channel_count(station.id)
    data["is_bot"] = bool(bot_ids and station.id in bot_ids)
    return data


async def _bot_station_ids(db: AsyncSession) -> set:
    return set((await db.execute(select(BotStation.station_id))).scalars().all())


class StationCreate(BaseModel):
    frequency: float
    callsign: str
    description: Optional[str] = ""
    ai_dj_prompt: Optional[str] = None
    # 開始時刻が未来なら「予約（RESERVED / 開局準備中）」として開局する
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class StationUpdate(BaseModel):
    callsign: Optional[str] = None
    description: Optional[str] = None
    theme_color: Optional[str] = None
    ai_dj_prompt: Optional[str] = None
    ai_dj_enabled: Optional[bool] = None


@router.get("/stations")
async def list_stations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Station).order_by(Station.frequency.asc()))
    bot_ids = await _bot_station_ids(db)
    return {
        "success": True,
        "stations": [_with_listeners(s, bot_ids) for s in result.scalars().all()],
    }


@router.get("/stations/available")
async def available_frequencies(
    band: str = "free", db: AsyncSession = Depends(get_db)
):
    """開局可能な空き周波数の一覧を返す。

    - band=free（既定）: 自由な周波数（誰でも開局・予約できる一般帯）
    - band=dedicated:    専用局（24時間常設）を作成できる帯
    """
    result = await db.execute(select(Station.frequency))
    used = {round(float(f), 1) for f in result.scalars().all()}
    key = "dedicated" if band == "dedicated" else "free"
    wanted = dedicated_frequencies() if key == "dedicated" else free_frequencies()
    info = bands_payload()
    band_info = next((b for b in info["bands"] if b["key"] == key), None)
    available = [f for f in wanted if f not in used]
    return {
        "success": True,
        "band": band_info,
        "bands": info["bands"],
        "count": len(available),
        "available": available,
    }


@router.get("/stations/mine")
async def my_stations(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Station).where(Station.owner_id == user.id).order_by(Station.frequency.asc())
    )
    bot_ids = await _bot_station_ids(db)
    return {
        "success": True,
        "stations": [_with_listeners(s, bot_ids) for s in result.scalars().all()],
    }


@router.get("/stations/{station_id}")
async def get_station(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    bot_ids = await _bot_station_ids(db)
    return {"success": True, "station": _with_listeners(station, bot_ids)}


@router.get("/stations/{station_id}/messages")
async def list_station_messages(
    station_id: int, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """ステーションのチャット履歴（新しい順に取得して古い順へ返す）。"""
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(Message)
        .where(Message.station_id == station_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return {"success": True, "messages": [m.to_dict() for m in messages]}


@router.get("/stations/{station_id}/tracks")
async def list_station_tracks(
    station_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """ステーションの再生ログ（過去に流れた曲）を新しい順に返す。"""
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    limit = max(1, min(limit, 200))
    rows = (
        await db.execute(
            select(SessionTrack, BroadcastSession)
            .join(BroadcastSession, SessionTrack.session_id == BroadcastSession.id)
            .where(BroadcastSession.station_id == station_id)
            .order_by(SessionTrack.id.desc())
            .limit(limit)
        )
    ).all()
    tracks = []
    for track, session in rows:
        data = track.to_dict()
        data["session_title"] = session.session_title
        data["session_started_at"] = (
            session.started_at.isoformat() if session.started_at else None
        )
        tracks.append(data)
    return {"success": True, "tracks": tracks}


async def _launch_station(data: StationCreate, user: User, db: AsyncSession) -> Station:
    """開局の共通処理（帯域・保有制約・排他チェック）。"""
    # 一般開局は「自由な周波数」（専用局帯以外）のみ
    freq = validate_free_frequency(data.frequency)
    if not data.callsign.strip():
        raise HTTPException(status_code=400, detail="コールサイン（局名）を入力してください")

    # 保有制約: 1ユーザーにつき1周波数まで（管理者を除く）
    if user.role != "admin":
        mine = (
            await db.execute(select(Station).where(Station.owner_id == user.id))
        ).scalars().first()
        if mine is not None:
            raise HTTPException(
                status_code=409,
                detail="1ユーザーにつき保有できる周波数は1つまでです（先に廃局してください）",
            )

    existing = (
        await db.execute(select(Station).where(Station.frequency == freq))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="この周波数は既に使用されています")

    now = datetime.now()
    active_res = (
        await db.execute(
            select(Reservation).where(
                Reservation.frequency == freq,
                Reservation.status == "active",
                Reservation.end_time > now,
            )
        )
    ).scalars().first()
    if active_res is not None:
        raise HTTPException(status_code=409, detail="この周波数は予約されています")

    # 開始時刻が未来なら RESERVED（開局準備中）、それ以外は即 LIVE
    status = "reserved" if (data.scheduled_start and data.scheduled_start > now) else "live"
    station = Station(
        owner_id=user.id,
        frequency=freq,
        callsign=data.callsign.strip(),
        description=data.description or "",
        ai_dj_prompt=data.ai_dj_prompt,
        status=status,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
    )
    db.add(station)
    await db.commit()
    await db.refresh(station)
    # 2chライクな最初のスレッド（第1スレ）を作成
    from app.services.threads import ensure_current_thread

    await ensure_current_thread(db, station)
    await db.commit()
    # 開局したらパーソナリティ権限へ昇格
    if user.role == "listener":
        user.role = "broadcaster"
        await db.commit()
    await broadcast_frequency_status(freq, status, station.id)
    return station


@router.post("/stations", status_code=201)
async def create_station(
    data: StationCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """開局（周波数の取得）。"""
    station = await _launch_station(data, user, db)
    return {"success": True, "station": _with_listeners(station)}


@router.post("/stations/launch", status_code=201)
async def launch_station(
    data: StationCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """本開局（正式開局申請）。POST /api/stations/launch"""
    station = await _launch_station(data, user, db)
    return {"success": True, "station": _with_listeners(station)}


@router.put("/stations/{station_id}")
async def update_station(
    station_id: int,
    data: StationUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="このステーションの編集権限がありません")
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(station, key, value)
    await db.commit()
    await db.refresh(station)
    return {"success": True, "station": _with_listeners(station)}


@router.post("/stations/{station_id}/youtube")
async def station_set_youtube(
    station_id: int,
    data: dict,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """BGMを強制切り替え（パーソナリティのみ）。"""
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="BGMを切り替えられるのは開局者だけです")
    video_id = parse_youtube_id(data.get("url") or data.get("video_id"))
    if not video_id:
        raise HTTPException(status_code=400, detail="YouTubeのURLまたは動画IDを正しく入力してください")
    was_live = station.status == "live"
    station.current_youtube_id = video_id
    station.playback_started_at = datetime.now()
    station.set_status("live")
    await db.commit()
    # 停波中から BGM で復帰した場合はセッションを開始する
    if not was_live:
        await open_session(db, station)
    # 選曲ログに記録（再生ログを即時更新できるよう WS にも載せる）
    track = await record_track(db, station_id, video_id)
    started_iso = station.playback_started_at.isoformat()
    await manager.broadcast(
        station_id,
        {
            "type": "track_update",
            "youtube_video_id": video_id,
            "playback_started_at": started_iso,
            "track": track.to_dict() if track else None,
        },
    )
    # 曲が切り替わったらDJが曲紹介コメントを投稿する（今流れている曲に連動）
    schedule_track_change(station_id, video_id, track.title if track else None)
    return {"success": True, "station": _with_listeners(station)}


@router.post("/stations/{station_id}/live")
async def station_set_live(
    station_id: int,
    data: dict,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """放送中／休止を切り替え。"""
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="権限がありません")
    new_live = bool(data.get("is_live", station.status != "live"))
    station.set_status("live" if new_live else "off_air")
    await db.commit()
    await broadcast_frequency_status(station.frequency, station.status, station.id)
    await manager.broadcast(
        station_id,
        {"type": "live_update", "is_live": station.status == "live", "status": station.status},
    )
    return {"success": True, "is_live": station.status == "live", "status": station.status}


@router.post("/stations/{station_id}/mute")
async def station_mute(
    station_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """BGMを停止（ミュート）。"""
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="権限がありません")
    station.current_youtube_id = None
    station.playback_started_at = None
    await db.commit()
    await manager.broadcast(
        station_id, {"type": "track_update", "youtube_video_id": None, "playback_started_at": None}
    )
    return {"success": True}


@router.delete("/stations/{station_id}/messages/{message_id}")
async def delete_message(
    station_id: int,
    message_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """チャットモデレーション（開局者／管理者のみ）。"""
    from app.models.models import Message

    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="モデレーション権限がありません")
    msg = await db.get(Message, message_id)
    if msg and msg.station_id == station_id:
        await db.delete(msg)
        await db.commit()
        await manager.broadcast(station_id, {"type": "message_deleted", "id": message_id})
    return {"success": True}


# ---- お気に入り ----

@router.get("/favorites")
async def my_favorites(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StationFavorite).where(StationFavorite.user_id == user.id)
    )
    favs = result.scalars().all()
    ids = [f.station_id for f in favs]
    stations = []
    if ids:
        res = await db.execute(select(Station).where(Station.id.in_(ids)).order_by(Station.frequency.asc()))
        stations = res.scalars().all()
    return {"success": True, "favorites": [_with_listeners(s) for s in stations]}


@router.post("/stations/{station_id}/favorite")
async def add_favorite(
    station_id: int, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    existing = await db.get(StationFavorite, (user.id, station_id))
    if not existing:
        db.add(StationFavorite(user_id=user.id, station_id=station_id))
        await db.commit()
    return {"success": True, "favorited": True}


@router.delete("/stations/{station_id}/favorite")
async def remove_favorite(
    station_id: int, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    existing = await db.get(StationFavorite, (user.id, station_id))
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"success": True, "favorited": False}


class BotReportIn2(BaseModel):
    """どの局でも使える「曲が終わった/再生できなかった」報告。"""

    video_id: Optional[str] = None
    # ended = 最後まで再生 / error = 埋め込み再生できなかった
    reason: Optional[str] = None


@router.post("/stations/{station_id}/track-ended")
async def track_ended(
    station_id: int,
    data: BotReportIn2,
    db: AsyncSession = Depends(get_db),
):
    """再生中の曲が終わった（または再生できなかった）ことをリスナーから受け取る。

    - 自動DJ局（DJ BOT / Vocaloid BOT）: 次の曲へ（`/bot/ended` と同じ）
    - 専用局（24時間常設）: 何もしない（自律運行エンジンが次曲を送出する）
    - 番組枠の放送中: 曲だけクリアして `live` を維持（番組終了時刻はタイムテーブルに任せる）
    - それ以外の通常局: 曲が尽きたら**停波（砂嵐）**にする

    通常局は次曲を自動で選ばないため、そのままだと最後の曲が何度も再生され
    砂嵐にならない（＝放送が終わらない）状態になる。ここで曲をクリアして
    停波することで、次のリクエスト/BGM設定まで砂嵐になる。
    """
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    # 報告された曲が「今オンエア中の曲」と一致するときだけ処理する（古い報告は無視）
    if not data.video_id or station.current_youtube_id != data.video_id:
        return {"success": True, "action": "ignored"}

    # 自動DJ局は次の曲へ
    if await db.get(BotStation, station_id) is not None:
        await play_next(db, station)
        return {"success": True, "action": "next"}

    # 専用局は自律運行エンジンに任せる
    if station.is_dedicated:
        return {"success": True, "action": "dedicated"}

    # 番組枠（タイムテーブル）で放送中か
    now = datetime.now()
    active_program = (
        await db.execute(
            select(Program.id)
            .where(
                Program.station_id == station_id,
                Program.start_time <= now,
                Program.end_time > now,
            )
            .limit(1)
        )
    ).scalars().first()

    # 曲をクリア（遅れて来たリスナーに同じ曲を再生させない）
    await clear_now_playing(db, station)
    if active_program is not None:
        # 番組枠の間は停波しない（曲だけクリアして放送は維持する）
        return {"success": True, "action": "cleared"}

    # 通常局は停波（砂嵐）して放送セッションを閉じる
    station.set_status("off_air")
    await db.commit()
    await close_session(db, station_id)
    await broadcast_frequency_status(station.frequency, "off_air", station.id)
    await manager.broadcast(
        station_id, {"type": "live_update", "is_live": False, "status": "off_air"}
    )
    await manager.broadcast(
        station_id,
        {
            "type": "system",
            "content": "📻 曲が終了しました。次の曲が設定されるまで砂嵐（OFF AIR）になります。",
            "listener_count": manager.channel_count(station_id),
        },
    )
    return {"success": True, "action": "off_air"}


# ---- エコシステム用プレビュー ----

@router.get("/preview")
async def preview(frequency: Optional[float] = None, db: AsyncSession = Depends(get_db)):
    """他サービス向けプレビュー（周波数・番組名・LIVEステータス）。"""
    if frequency is None:
        raise HTTPException(status_code=400, detail="frequency を指定してください")
    result = await db.execute(select(Station).where(Station.frequency == round(frequency, 1)))
    station = result.scalars().first()
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    return {
        "success": True,
        "frequency": station.frequency,
        "name": station.callsign,
        "description": station.description,
        "is_live": station.status == "live",
        "status": station.status,
        "listener_count": manager.channel_count(station.id),
        "youtube_video_id": station.current_youtube_id,
    }
