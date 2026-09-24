"""公開アーカイブ API（Public Auto-Archiving System）。

認証ヘッダー不要。予約の有無を問わず自動記録された放送セッションを、
誰でも閲覧・タイムシフト再生できる。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import BroadcastSession, Message, Station

router = APIRouter(prefix="/api", tags=["archives"])


@router.get("/archives")
async def list_archives(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """公開アーカイブ（全ステーションの放送セッション＝スレッド）を新しい順に返す。

    ステーションが削除済みの孤立セッションは除外する（frequency/callsign が null になるため）。
    各スレッドのメッセージ件数も付与する。
    """
    from datetime import datetime

    from sqlalchemy import and_, func, or_

    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(BroadcastSession)
        .join(Station, BroadcastSession.station_id == Station.id)
        .where(BroadcastSession.is_public.is_(True))
        .order_by(BroadcastSession.started_at.desc(), BroadcastSession.id.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    out = []
    for s in sessions:
        data = s.to_dict()
        end = s.ended_at or datetime.now()
        cond = Message.session_id == s.id
        if s.started_at is not None:
            cond = or_(
                cond,
                and_(
                    Message.station_id == s.station_id,
                    Message.created_at >= s.started_at,
                    Message.created_at <= end,
                ),
            )
        count = (
            await db.execute(select(func.count(Message.id)).where(cond))
        ).scalar() or 0
        data["total_messages"] = int(count)
        out.append(data)
    return {"success": True, "sessions": out}


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
    """セッション（スレッド）詳細。放送時間帯のチャットログを返す。"""
    from datetime import datetime

    from sqlalchemy import and_, or_

    session = await db.get(BroadcastSession, session_id)
    if session is None or not session.is_public:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    # セッションに紐づくメッセージに加え、放送時間帯（同じ局）のメッセージも拾う。
    # これにより session_id が未設定のメッセージもスレッドに含まれる。
    end = session.ended_at or datetime.now()
    start = session.started_at
    cond = Message.session_id == session_id
    if start is not None:
        cond = or_(
            cond,
            and_(
                Message.station_id == session.station_id,
                Message.created_at >= start,
                Message.created_at <= end,
            ),
        )
    messages = (
        await db.execute(select(Message).where(cond).order_by(Message.id.asc()))
    ).scalars().all()

    return {
        "success": True,
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }
