"""プロフィール（マイページ）API。

ログインユーザーの基本情報・統計・保有局・選曲ログ・過去の放送セッションを返す。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_user
from app.models.models import (
    BroadcastSession,
    Message,
    SessionTrack,
    Station,
    StationFavorite,
    User,
)

router = APIRouter(prefix="/api", tags=["me"])


async def _owned_station_ids(db: AsyncSession, user: User) -> list[int]:
    return list(
        (
            await db.execute(select(Station.id).where(Station.owner_id == user.id))
        ).scalars().all()
    )


@router.get("/me")
async def my_profile(
    user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    """基本情報と統計（局数 / 放送セッション数 / 曲ログ数 / メッセージ数 / お気に入り数）。"""
    station_ids = await _owned_station_ids(db, user)

    session_ids: list[int] = []
    if station_ids:
        session_ids = list(
            (
                await db.execute(
                    select(BroadcastSession.id).where(
                        BroadcastSession.station_id.in_(station_ids)
                    )
                )
            ).scalars().all()
        )

    track_count = 0
    if session_ids:
        track_count = int(
            (
                await db.execute(
                    select(func.count(SessionTrack.id)).where(
                        SessionTrack.session_id.in_(session_ids)
                    )
                )
            ).scalar()
            or 0
        )

    message_count = 0
    if station_ids:
        message_count = int(
            (
                await db.execute(
                    select(func.count(Message.id)).where(
                        Message.station_id.in_(station_ids)
                    )
                )
            ).scalar()
            or 0
        )

    favorite_count = int(
        (
            await db.execute(
                select(func.count(StationFavorite.station_id)).where(
                    StationFavorite.user_id == user.id
                )
            )
        ).scalar()
        or 0
    )

    return {
        "success": True,
        "user": user.to_dict(),
        "stats": {
            "stations": len(station_ids),
            "sessions": len(session_ids),
            "tracks": track_count,
            "messages": message_count,
            "favorites": favorite_count,
        },
    }


@router.get("/me/tracks")
async def my_tracks(
    limit: int = 100,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """保有局で放送中に流れた曲（選曲ログ）を新しい順に返す。"""
    limit = max(1, min(limit, 300))
    rows = (
        await db.execute(
            select(SessionTrack, BroadcastSession, Station)
            .join(BroadcastSession, SessionTrack.session_id == BroadcastSession.id)
            .join(Station, BroadcastSession.station_id == Station.id)
            .where(Station.owner_id == user.id)
            .order_by(SessionTrack.id.desc())
            .limit(limit)
        )
    ).all()

    tracks = []
    for track, session, station in rows:
        data = track.to_dict()
        data["station_id"] = station.id
        data["station_callsign"] = station.callsign
        data["frequency"] = station.frequency
        data["session_title"] = session.session_title
        data["session_started_at"] = (
            session.started_at.isoformat() if session.started_at else None
        )
        tracks.append(data)
    return {"success": True, "tracks": tracks}


@router.get("/me/sessions")
async def my_sessions(
    limit: int = 50,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """保有局の過去の放送セッションを新しい順に返す。"""
    limit = max(1, min(limit, 200))
    rows = (
        await db.execute(
            select(BroadcastSession, Station)
            .join(Station, BroadcastSession.station_id == Station.id)
            .where(Station.owner_id == user.id)
            .order_by(BroadcastSession.started_at.desc(), BroadcastSession.id.desc())
            .limit(limit)
        )
    ).all()

    sessions = []
    for session, station in rows:
        data = session.to_dict()
        data["station_callsign"] = station.callsign
        data["frequency"] = station.frequency
        sessions.append(data)
    return {"success": True, "sessions": sessions}
