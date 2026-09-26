"""チャット・DJ・bot の発言を「現在スレッド」へ紐づけて保存する共通処理。

掲示板のチャット欄は現在スレッド（`thread_id`）の投稿だけを表示するため、
スレッドへ紐づけずに保存すると**投稿がログから消える**（入り直すと会話が
リセットされたように見える）。すべての発言はこの関数を通すこと。
"""
from typing import Optional

from app.core.database import async_session_factory
from app.models.models import Message, Station
from app.services.sessions import current_offset
from app.services.threads import ensure_current_thread, register_post
from app.services.websocket_manager import manager


async def persist_message(
    station_id: int,
    sender_name: str,
    content: str,
    user_id: Optional[int] = None,
    is_dj: bool = False,
    is_broadcaster: bool = False,
    youtube_id: Optional[str] = None,
) -> dict:
    """1件保存して、配信に使う payload（dict）を返す。

    - 現在スレッドへ紐づける（上限で自動アーカイブ＋新スレ）
    - 放送セッションへ自動バインド（offset = セッション開始からの経過秒）
    """
    async with async_session_factory() as session:
        station = await session.get(Station, station_id)
        thread = await ensure_current_thread(session, station) if station else None
        session_id, offset = await current_offset(session, station_id)
        msg = Message(
            station_id=station_id,
            session_id=session_id,
            thread_id=thread.id if thread else None,
            offset_seconds=offset,
            user_id=user_id,
            sender_name=sender_name,
            content=content,
            youtube_id=youtube_id,
            is_dj=is_dj,
            is_broadcaster=is_broadcaster,
        )
        session.add(msg)
        rolled = await register_post(session, station, thread) if thread else None
        await session.commit()
        await session.refresh(msg)
        payload = msg.to_dict()

    if rolled is not None:
        # 新スレに切り替わったことを全クライアントへ通知
        await manager.broadcast(
            station_id, {"type": "thread_update", "thread": rolled.to_dict()}
        )
    return payload
