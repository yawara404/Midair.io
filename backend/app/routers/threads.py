"""掲示板スレッド API（2chライク）。

- 局の現在スレッド／過去スレッド一覧
- スレッド詳細（投稿ログ）
- 全アーカイブ（過去スレッド）一覧
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Message, Station, Thread
from app.services.threads import MAX_THREAD_POSTS

router = APIRouter(prefix="/api", tags=["threads"])


@router.get("/stations/{station_id}/thread")
async def current_thread(station_id: int, db: AsyncSession = Depends(get_db)):
    """局の現在スレッドと、その投稿ログを返す。"""
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    thread = (
        await db.execute(
            select(Thread)
            .where(Thread.station_id == station_id, Thread.is_archived.is_(False))
            .order_by(Thread.number.desc())
            .limit(1)
        )
    ).scalars().first()
    messages = []
    if thread is not None:
        messages = (
            await db.execute(
                select(Message).where(Message.thread_id == thread.id).order_by(Message.id.asc())
            )
        ).scalars().all()
    return {
        "success": True,
        "max_posts": MAX_THREAD_POSTS,
        "thread": thread.to_dict() if thread else None,
        "messages": [m.to_dict() for m in messages],
    }


@router.get("/stations/{station_id}/threads")
async def list_station_threads(station_id: int, db: AsyncSession = Depends(get_db)):
    """局の全スレッド（現在＋過去）を新しい順に返す。"""
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    threads = (
        await db.execute(
            select(Thread)
            .where(Thread.station_id == station_id)
            .order_by(Thread.number.desc())
        )
    ).scalars().all()
    return {
        "success": True,
        "max_posts": MAX_THREAD_POSTS,
        "threads": [t.to_dict() for t in threads],
    }


@router.get("/threads")
async def list_threads(
    archived: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """全ステーションのスレッド一覧（新しい順）。archived=1 で過去スレのみ。"""
    limit = max(1, min(limit, 300))
    stmt = (
        select(Thread)
        .join(Station, Thread.station_id == Station.id)
        .order_by(Thread.created_at.desc(), Thread.id.desc())
        .limit(limit)
    )
    if archived:
        stmt = stmt.where(Thread.is_archived.is_(True))
    threads = (await db.execute(stmt)).scalars().all()
    return {
        "success": True,
        "max_posts": MAX_THREAD_POSTS,
        "threads": [t.to_dict() for t in threads],
    }


@router.get("/threads/{thread_id}")
async def thread_detail(thread_id: int, db: AsyncSession = Depends(get_db)):
    """スレッド詳細（過去の掲示板画面）を返す。"""
    thread = await db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="スレッドが見つかりません")
    messages = (
        await db.execute(
            select(Message).where(Message.thread_id == thread_id).order_by(Message.id.asc())
        )
    ).scalars().all()
    return {
        "success": True,
        "max_posts": MAX_THREAD_POSTS,
        "thread": thread.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }
