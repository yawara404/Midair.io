"""曲が切り替わった瞬間のDJ曲紹介コメント（今オンエア中の曲に連動）。

- 自動DJ局（DJ BOT / Vocaloid BOT）・専用局・パーソナリティのBGM切替から
  `schedule_track_change()` で呼ばれる（呼び出し元は待たない）。
- 「今流れている曲」を曲名で LLM に渡し、局のキャラクター設定（ai_dj_prompt）
  として自由に曲紹介を書かせる。定型文のリストは使わない。
- LLM 未設定・失敗時は何も投稿しない。
- dj_track_intro_* 設定でオン/オフ・連投防止・リスナー有無の条件を切り替えられる。
"""
import asyncio
import time
from typing import Optional

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.models import Station
from app.services.ai_dj import generate_track_intro, is_llm_configured
from app.services.sessions import (
    recent_chat_context,
    recent_track_titles,
    resolve_track_title,
)
from app.services.websocket_manager import manager

# 局ごとの最終曲紹介時刻（同じ局で連投しない）
_last_intro: dict[int, float] = {}

# バックグラウンドタスクの参照（GC で消えないように保持する）
_tasks: set[asyncio.Task] = set()


def schedule_track_change(
    station_id: int, youtube_id: Optional[str], title: Optional[str] = None
) -> None:
    """曲の切り替えをDJの曲紹介コメントとして投稿する（呼び出し元は待たない）。"""
    if not settings.dj_track_intro_enabled or not youtube_id:
        return
    task = asyncio.create_task(announce_track_change(station_id, youtube_id, title))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def announce_track_change(
    station_id: int, youtube_id: Optional[str], title: Optional[str] = None
) -> bool:
    """今オンエア中の曲をDJが紹介する（投稿できたら True）。"""
    if not settings.dj_track_intro_enabled or not youtube_id:
        return False
    if not is_llm_configured():
        return False
    if (
        settings.dj_track_intro_requires_listener
        and manager.channel_count(station_id) <= 0
    ):
        return False
    if time.time() - _last_intro.get(station_id, 0.0) < max(
        0, settings.dj_track_intro_cooldown_seconds
    ):
        return False

    # 曲名・直前の曲・会話・キャラ設定を集める（LLM 呼び出しの前にDBを閉じる）
    async with async_session_factory() as session:
        station = await session.get(Station, station_id)
        if station is None or not station.ai_dj_enabled:
            return False
        # 生成を待つ間に次の曲へ切り替わっていたら、古い曲の紹介は投稿しない
        if station.current_youtube_id and station.current_youtube_id != youtube_id:
            return False
        program = station.callsign
        persona = station.ai_dj_prompt
        resolved = await resolve_track_title(session, station_id, youtube_id, title)
        previous = await recent_track_titles(
            session, station_id, limit=2, exclude_id=youtube_id
        )
        context = await recent_chat_context(session, station_id)

    # 曲名が取れないときは動画IDを読み上げないよう、曲紹介自体を見送る
    if not resolved or resolved == youtube_id:
        return False
    _last_intro[station_id] = time.time()

    line = await generate_track_intro(
        program,
        persona,
        resolved,
        previous=" → ".join(previous),
        context=context,
    )
    if not line:
        return False

    # Discord 連携局（Miaちゃん）は本人名義で投稿する
    sender = "Mia" if program == settings.discord_station_callsign else "DJ"
    # 循環import回避のため関数内で読み込む（main.py と同じ書き方）
    from app.routers.ws import _persist_message

    payload = await _persist_message(station_id, sender, line, is_dj=True)
    await manager.broadcast(station_id, {"type": "message", **payload})
    manager.touch(station_id)
    return True
