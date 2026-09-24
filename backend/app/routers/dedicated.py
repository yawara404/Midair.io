"""専用局（24時間常設）の申請・審査・承認 API。

- listener: 申請の作成・自分の申請一覧
- admin:    申請の一覧・承認・却下（承認で Station を本登録しライブラリ移行）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_user
from app.core.utils import parse_youtube_id
from app.models.models import (
    DedicatedApplication,
    DedicatedTrackLibrary,
    Station,
    User,
)
from app.routers.frequencies import broadcast_frequency_status
from app.services.dedicated import (
    advance_station,
    resolve_track_meta,
    seed_initial_library,
)
from app.services.sessions import open_session

router = APIRouter(prefix="/api", tags=["dedicated"])

# 1申請あたりの初期音源の上限
_MAX_INITIAL_TRACKS = 100


def _require_admin(user: User) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return user


class ApplyIn(BaseModel):
    desired_frequency: float
    callsign: str
    station_title: str
    genre: Optional[str] = "general"
    concept_description: Optional[str] = ""
    ai_dj_concept: Optional[str] = None
    # ["<URL/ID>", ...] または [{"youtube_id","title"}, ...]
    initial_tracks: list = []


class ReviewIn(BaseModel):
    note: Optional[str] = None


async def _frequency_status(db: AsyncSession, freq: float) -> str:
    existing = (
        await db.execute(
            select(Station).where(Station.frequency == round(freq, 1))
        )
    ).scalars().first()
    return "used" if existing else "free"


@router.get("/dedicated/genres")
async def dedicated_genres():
    """専用局で選べるジャンルの一覧。"""
    return {
        "success": True,
        "genres": [
            "general",
            "ambient",
            "lofi",
            "rock",
            "vocaloid",
            "jazz",
            "electronic",
            "talk",
        ],
    }


@router.post("/dedicated/apply", status_code=201)
async def apply_dedicated(
    data: ApplyIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """専用局の開設申請（listener 以上）。"""
    freq = round(float(data.desired_frequency), 1)
    if freq < settings.station_freq_min or freq > settings.station_freq_max:
        raise HTTPException(
            status_code=400,
            detail=f"周波数は{settings.station_freq_min:.1f}〜{settings.station_freq_max:.1f}MHzの範囲で指定してください",
        )
    if not (data.callsign or "").strip():
        raise HTTPException(status_code=400, detail="コールサイン（局名）を入力してください")
    if not (data.station_title or "").strip():
        raise HTTPException(status_code=400, detail="ステーション名（番組名）を入力してください")
    if not (data.concept_description or "").strip():
        raise HTTPException(status_code=400, detail="放送コンセプトを入力してください")

    # 同じ周波数に「審査中」の申請が重複しないようにする
    pending = (
        await db.execute(
            select(DedicatedApplication).where(
                DedicatedApplication.desired_frequency == freq,
                DedicatedApplication.status == "pending",
            )
        )
    ).scalars().first()
    if pending is not None:
        raise HTTPException(status_code=409, detail="この周波数は審査中の申請があります")

    # 初期音源リストを正規化（URL/ID → {youtube_id, title}）
    import json

    tracks: list[dict] = []
    for item in (data.initial_tracks or [])[:_MAX_INITIAL_TRACKS]:
        if isinstance(item, str):
            video_id = parse_youtube_id(item)
            title = None
        elif isinstance(item, dict):
            video_id = parse_youtube_id(item.get("youtube_id") or item.get("url"))
            title = item.get("title")
        else:
            continue
        if not video_id:
            continue
        meta = await resolve_track_meta(video_id, title)
        tracks.append(meta)

    application = DedicatedApplication(
        applicant_id=user.id,
        desired_frequency=freq,
        callsign=data.callsign.strip(),
        station_title=data.station_title.strip(),
        genre=(data.genre or "general").strip(),
        concept_description=(data.concept_description or "").strip(),
        initial_tracks_json=json.dumps(tracks, ensure_ascii=False),
        ai_dj_concept=data.ai_dj_concept,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return {"success": True, "application": application.to_dict()}


@router.get("/dedicated/applications/mine")
async def my_applications(
    user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    """自分の専用局申請一覧（新しい順）。"""
    result = await db.execute(
        select(DedicatedApplication)
        .where(DedicatedApplication.applicant_id == user.id)
        .order_by(DedicatedApplication.id.desc())
    )
    return {"success": True, "applications": [a.to_dict() for a in result.scalars().all()]}


# ---- 管理者向け ----


@router.get("/admin/applications")
async def admin_list_applications(
    status: Optional[str] = None,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """専用局申請の一覧（管理者）。status で絞り込み可能。"""
    _require_admin(user)
    stmt = select(DedicatedApplication).order_by(DedicatedApplication.id.desc())
    if status:
        stmt = stmt.where(DedicatedApplication.status == status)
    result = await db.execute(stmt)
    return {"success": True, "applications": [a.to_dict() for a in result.scalars().all()]}


@router.get("/admin/applications/stats")
async def admin_application_stats(
    user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    _require_admin(user)
    from sqlalchemy import func

    rows = (
        await db.execute(
            select(DedicatedApplication.status, func.count(DedicatedApplication.id)).group_by(
                DedicatedApplication.status
            )
        )
    ).all()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for status, count in rows:
        counts[status] = int(count)
    return {"success": True, "counts": counts}


@router.post("/admin/applications/{application_id}/approve")
async def admin_approve_application(
    application_id: int,
    data: ReviewIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """申請を承認し、専用局を本登録する。"""
    _require_admin(user)
    application = await db.get(DedicatedApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="申請が見つかりません")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="この申請は既に審査済みです")

    freq = round(float(application.desired_frequency), 1)
    existing = (
        await db.execute(select(Station).where(Station.frequency == freq))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="希望周波数は既に使用されています")

    # 専用局の本登録（周波数固定）
    station = Station(
        owner_id=application.applicant_id,
        frequency=freq,
        callsign=application.callsign,
        description=application.concept_description,
        status="off_air",
        is_dedicated=True,
        dedicated_genre=application.genre,
        ai_dj_enabled=True,
        ai_dj_prompt=application.ai_dj_concept,
    )
    db.add(station)
    await db.commit()
    await db.refresh(station)

    # 2chライクな最初のスレッドを作成
    from app.services.threads import ensure_current_thread

    await ensure_current_thread(db, station)
    await db.commit()

    # 初期選曲リストをライブラリへ移行
    import json

    try:
        tracks = json.loads(application.initial_tracks_json or "[]")
    except Exception:
        tracks = []
    await seed_initial_library(db, station, tracks)

    # 申請者を dedicated_owner へ昇格
    applicant = await db.get(User, application.applicant_id)
    if applicant is not None and applicant.role in ("listener", "broadcaster"):
        applicant.role = "dedicated_owner"
        await db.commit()

    # セッションを開始し、最初の曲を送出して ON AIR
    await open_session(db, station, title=f"{station.callsign} 放送")
    await advance_station(db, station)
    await broadcast_frequency_status(freq, "live", station.id)

    application.status = "approved"
    application.review_note = data.note
    application.reviewed_by = user.id
    application.reviewed_at = datetime.now()
    await db.commit()
    await db.refresh(application)

    return {"success": True, "application": application.to_dict(), "station": station.to_dict()}


@router.post("/admin/applications/{application_id}/reject")
async def admin_reject_application(
    application_id: int,
    data: ReviewIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """申請を却下する（理由を記録）。"""
    _require_admin(user)
    application = await db.get(DedicatedApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="申請が見つかりません")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="この申請は既に審査済みです")

    application.status = "rejected"
    application.review_note = data.note
    application.reviewed_by = user.id
    application.reviewed_at = datetime.now()
    await db.commit()
    await db.refresh(application)
    return {"success": True, "application": application.to_dict()}


# ---- 専用局のライブラリ・キュー管理（所有者/管理者） ----


def _require_station_owner(station: Optional[Station], user: User) -> Station:
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="この専用局の権限がありません")
    return station


class LibraryTrackIn(BaseModel):
    url: Optional[str] = None
    video_id: Optional[str] = None
    title: Optional[str] = None


@router.get("/dedicated/{station_id}/library")
async def get_library(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if station is None or not station.is_dedicated:
        raise HTTPException(status_code=404, detail="専用局が見つかりません")
    tracks = (
        await db.execute(
            select(DedicatedTrackLibrary)
            .where(DedicatedTrackLibrary.station_id == station_id)
            .order_by(DedicatedTrackLibrary.id.asc())
        )
    ).scalars().all()
    return {"success": True, "tracks": [t.to_dict() for t in tracks]}


@router.post("/dedicated/{station_id}/library", status_code=201)
async def add_library_track(
    station_id: int,
    data: LibraryTrackIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    station = _require_station_owner(await db.get(Station, station_id), user)
    if not station.is_dedicated:
        raise HTTPException(status_code=400, detail="専用局ではありません")
    video_id = parse_youtube_id(data.video_id or data.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="YouTubeのURLまたは動画IDを正しく入力してください")
    meta = await resolve_track_meta(video_id, data.title)
    track = DedicatedTrackLibrary(
        station_id=station_id,
        youtube_id=meta["youtube_id"],
        title=meta["title"],
        duration_seconds=meta["duration_seconds"],
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return {"success": True, "track": track.to_dict()}


@router.delete("/dedicated/{station_id}/library/{track_id}")
async def remove_library_track(
    station_id: int,
    track_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    _require_station_owner(await db.get(Station, station_id), user)
    track = await db.get(DedicatedTrackLibrary, track_id)
    if track and track.station_id == station_id:
        await db.delete(track)
        await db.commit()
    return {"success": True}
