"""2chライクな掲示板スレッドの管理。

- 局ごとに「第Nスレ」を持ち、投稿が MAX_THREAD_POSTS に達すると自動で
  アーカイブ化し、次のスレッドを作成する。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Station, Thread

# 1スレッドの最大投稿数（これを超えると新スレへ）
MAX_THREAD_POSTS = 1000


def thread_title(station: Station, number: int) -> str:
    return f"{station.callsign} 第{number}スレ"


async def get_current_thread(db: AsyncSession, station_id: int) -> Optional[Thread]:
    """未アーカイブの現在スレッドを返す。"""
    return (
        await db.execute(
            select(Thread)
            .where(Thread.station_id == station_id, Thread.is_archived.is_(False))
            .order_by(Thread.number.desc())
            .limit(1)
        )
    ).scalars().first()


async def _next_number(db: AsyncSession, station_id: int) -> int:
    n = (
        await db.execute(
            select(func.max(Thread.number)).where(Thread.station_id == station_id)
        )
    ).scalar()
    return int(n or 0) + 1


async def create_thread(db: AsyncSession, station: Station) -> Thread:
    """次の番号のスレッドを新規作成する（未コミット）。"""
    number = await _next_number(db, station.id)
    thread = Thread(
        station_id=station.id,
        number=number,
        title=thread_title(station, number),
        post_count=0,
        is_archived=False,
    )
    db.add(thread)
    await db.flush()
    return thread


async def ensure_current_thread(db: AsyncSession, station: Station) -> Thread:
    """現在スレッドを返す。無ければ作成する。"""
    thread = await get_current_thread(db, station.id)
    if thread is not None:
        return thread
    return await create_thread(db, station)


async def register_post(db: AsyncSession, station: Station, thread: Thread) -> Optional[Thread]:
    """1投稿を登録し、上限に達したらアーカイブして新スレを作成する。

    新スレを作成した場合はその Thread を返す（コミットは呼び出し側）。
    """
    thread.post_count = (thread.post_count or 0) + 1
    rolled: Optional[Thread] = None
    if thread.post_count >= MAX_THREAD_POSTS:
        thread.is_archived = True
        thread.archived_at = datetime.now()
        rolled = await create_thread(db, station)
    return rolled


async def ensure_all_stations(db: AsyncSession) -> None:
    """全ステーションに現在スレッドがあることを保証する（起動時など）。

    スレッドが無い局には第1スレを作成し、既存メッセージ（thread_id 未設定）を
    そのスレッドへ割り当てて、過去ログとして閲覧できるようにする。
    """
    from app.models.models import Message

    stations = (await db.execute(select(Station))).scalars().all()
    for st in stations:
        thread = await get_current_thread(db, st.id)
        if thread is not None:
            continue
        thread = await create_thread(db, st)
        # 既存の未割り当てメッセージをこのスレッドへ
        msgs = (
            await db.execute(
                select(Message).where(
                    Message.station_id == st.id, Message.thread_id.is_(None)
                )
            )
        ).scalars().all()
        for m in msgs:
            m.thread_id = thread.id
        thread.post_count = len(msgs)
    await db.commit()
