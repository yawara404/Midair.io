"""公開アーカイブ API（Public Auto-Archiving System）。

認証ヘッダー不要。予約の有無を問わず自動記録された放送セッションを、
誰でも閲覧・タイムシフト再生できる。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import BroadcastSession, Message, SessionTrack, Station

router = APIRouter(prefix="/api", tags=["archives"])


@router.get("/archives")
async def list_archives(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """公開アーカイブ（全ステーションの放送セッション）を新しい順に返す。

    ステーションが削除済みの孤立セッションは除外する（frequency/callsign が null になるため）。
    """
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(BroadcastSession)
        .join(Station, BroadcastSession.station_id == Station.id)
        .where(BroadcastSession.is_public.is_(True))
        .order_by(BroadcastSession.started_at.desc(), BroadcastSession.id.desc())
        .limit(limit)
    )
    return {"success": True, "sessions": [s.to_dict() for s in result.scalars().all()]}


@router.get("/stations/{station_id}/archives")
async def station_archives(
    station_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """指定ステーションの公開アーカイブ一覧（認証不要）。"""
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(BroadcastSession)
        .where(
            BroadcastSession.station_id == station_id,
            BroadcastSession.is_public.is_(True),
        )
        .order_by(BroadcastSession.started_at.desc(), BroadcastSession.id.desc())
        .limit(limit)
    )
    return {"success": True, "sessions": [s.to_dict() for s in result.scalars().all()]}


@router.get("/sessions/{session_id}")
async def session_detail(session_id: int, db: AsyncSession = Depends(get_db)):
    """セッション詳細（メッセージログ＋選曲履歴）を返す。タイムシフト再生用。"""
    session = await db.get(BroadcastSession, session_id)
    if session is None or not session.is_public:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    messages = (
        await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.offset_seconds.asc(), Message.id.asc())
        )
    ).scalars().all()
    tracks = (
        await db.execute(
            select(SessionTrack)
            .where(SessionTrack.session_id == session_id)
            .order_by(SessionTrack.started_offset_sec.asc(), SessionTrack.id.asc())
        )
    ).scalars().all()

    return {
        "success": True,
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
        "tracks": [t.to_dict() for t in tracks],
    }
