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


async def resolve_track_title(
    db: AsyncSession, station_id: int, youtube_id: str, title: Optional[str] = None
) -> str:
    """曲名を解決する（渡された title → 選曲ログ → YouTube 情報 の順）。

    DJコメントに「今流れている曲」を渡すために使う。
    どの方法でも分からないときは動画IDを返す。
    """
    if title:
        return title
    if not youtube_id:
        return ""
    session = await get_open_session(db, station_id)
    if session is not None:
        logged = (
            await db.execute(
                select(SessionTrack.title)
                .where(
                    SessionTrack.session_id == session.id,
                    SessionTrack.youtube_id == youtube_id,
                )
                .order_by(SessionTrack.id.desc())
            )
        ).scalars().first()
        if logged:
            return logged
    fetched = await fetch_youtube_title(youtube_id)
    return fetched or youtube_id


async def current_track(db: AsyncSession, station: Station) -> dict:
    """今オンエア中の曲 {youtube_id, title} を返す（曲が無ければ空の辞書）。"""
    if not station.current_youtube_id:
        return {}
    return {
        "youtube_id": station.current_youtube_id,
        "title": await resolve_track_title(db, station.id, station.current_youtube_id),
    }


async def recent_track_titles(
    db: AsyncSession, station_id: int, limit: int = 5, exclude_id: Optional[str] = None
) -> list[str]:
    """直近に流れた曲名を新しい順に返す（exclude_id の曲を除ける）。DJコメントの話題づくりに使う。"""
    if limit <= 0:
        return []
    query = (
        select(SessionTrack.title)
        .join(BroadcastSession, SessionTrack.session_id == BroadcastSession.id)
        .where(BroadcastSession.station_id == station_id)
    )
    if exclude_id:
        query = query.where(SessionTrack.youtube_id != exclude_id)
    query = query.order_by(SessionTrack.id.desc()).limit(limit)
    return [title for title in (await db.execute(query)).scalars() if title]


async def dj_track_context(
    db: AsyncSession, station: Station
) -> tuple[Optional[str], Optional[str]]:
    """DJコメント用の「今オンエア中の曲名」と「直前までの曲名（A → B 形式）」を返す。

    ai_dj.generate_dj_line(track=..., recent=...) にそのまま渡せる形。
    """
    info = await current_track(db, station)
    recent = await recent_track_titles(
        db, station.id, limit=3, exclude_id=info.get("youtube_id")
    )
    return info.get("title"), " → ".join(recent)


async def recent_chat_context(
    db: AsyncSession, station_id: int, limit: int = 6
) -> str:
    """直近のチャットを「名前: 内容」で連結して返す（DJコメントの文脈用）。"""
    rows = (
        await db.execute(
            select(Message)
            .where(Message.station_id == station_id)
            .order_by(Message.id.desc())
            .limit(max(1, limit))
        )
    ).scalars().all()
    return "\n".join(f"{m.sender_name}: {m.content}" for m in reversed(rows))


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
