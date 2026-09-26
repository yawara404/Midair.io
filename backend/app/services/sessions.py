"""放送セッションの自動記録（ON AIR〜OFF AIR）ヘルパー。

番組予約の有無を問わず、ON AIR した瞬間にセッションを自動発行し、
メッセージ・選曲を offset（開始からの経過秒）付きでバインドする。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import BroadcastSession, Message, SessionTrack, Station
from app.services.youtube import fetch_youtube_title


def _now() -> datetime:
    return datetime.now()


async def get_open_session(
    db: AsyncSession, station_id: int
) -> Optional[BroadcastSession]:
    result = await db.execute(
        select(BroadcastSession)
        .where(
            BroadcastSession.station_id == station_id,
            BroadcastSession.ended_at.is_(None),
        )
        .order_by(BroadcastSession.id.desc())
    )
    return result.scalars().first()


async def open_session(
    db: AsyncSession, station: Station, title: Optional[str] = None
) -> BroadcastSession:
    """ON AIR 時に新しい放送セッションを自動発行する。"""
    existing = await get_open_session(db, station.id)
    if existing is not None:
        await close_session(db, station.id)
    session = BroadcastSession(
        station_id=station.id,
        session_title=(title or "突発ゲリラ放送")[:150],
        started_at=_now(),
        ended_at=None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def close_session(
    db: AsyncSession, station_id: int
) -> Optional[BroadcastSession]:
    """OFF AIR 時にセッションを自動クローズ（終了時刻を打刻・集計）。"""
    session = await get_open_session(db, station_id)
    if session is None:
        return None
    session.ended_at = _now()
    count = await db.execute(
        select(func.count(Message.id)).where(Message.session_id == session.id)
    )
    session.total_messages = int(count.scalar() or 0)
    await db.commit()
    await db.refresh(session)
    return session


async def current_offset(
    db: AsyncSession, station_id: int
) -> tuple[Optional[int], int]:
    """現在のオープンセッションIDと、開始からの経過秒を返す。"""
    session = await get_open_session(db, station_id)
    if session is None:
        return None, 0
    offset = max(0, int((_now() - session.started_at).total_seconds()))
    return session.id, offset


async def record_track(
    db: AsyncSession, station_id: int, youtube_id: str, title: Optional[str] = None
) -> Optional[SessionTrack]:
    """セッション中に流れた曲を、開始オフセット付きで記録して返す。

    戻り値を WebSocket の track_update に載せると、リスナーの再生ログを
    リロードなしで即時更新できる。
    """
    session = await get_open_session(db, station_id)
    if session is None:
        return None
    if title is None:
        # YOUTUBE_API_KEY があれば曲タイトルも取得して保存する
        title = await fetch_youtube_title(youtube_id)
    offset = max(0, int((_now() - session.started_at).total_seconds()))
    track = SessionTrack(
        session_id=session.id,
        youtube_id=youtube_id,
        title=title,
        started_offset_sec=offset,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return track
