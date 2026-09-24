"""自動DJ局（DJ BOT）の選曲・再生ロジック。

- 曲が終わったら次の曲へ（曲の長さを基に判定）
- 長すぎる曲は dj_bot_max_seconds（既定10分）で途中スキップ
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Station
from app.services.discord_sync import send_to_discord
from app.services.sessions import record_track
from app.services.trending import random_track
from app.services.websocket_manager import manager
from app.services.youtube import fetch_video_duration

# 局名 -> 選曲ソース設定（callsign で判定）
BOT_SOURCES: dict[str, dict] = {
    "DJ BOT": {"source": "trending", "query": None},
    "Vocaloid BOT": {"source": "search", "query": "VOCALOID ボカロ 初音ミク"},
}

# 局名 -> 既定周波数（範囲外になった自動DJ局を範囲内へ移すのにも使う）
BOT_FREQ_HINTS: dict[str, float] = {
    "DJ BOT": 84.0,
    "Vocaloid BOT": 85.0,
}


def resolve_source(station: Station) -> dict:
    return BOT_SOURCES.get(
        station.callsign, {"source": "trending", "query": None}
    )


# 動画ID -> 長さ（秒）のキャッシュ
_durations: dict[str, int] = {}


def set_duration(video_id: Optional[str], seconds: Optional[int]) -> None:
    if video_id and seconds:
        _durations[video_id] = int(seconds)


async def _duration_of(video_id: Optional[str]) -> Optional[int]:
    if not video_id:
        return None
    if video_id in _durations:
        return _durations[video_id]
    seconds = await fetch_video_duration(video_id)
    set_duration(video_id, seconds)
    return seconds


async def play_limit_seconds(video_id: Optional[str]) -> int:
    """この曲を流す秒数（曲の長さ。ただし最大 dj_bot_max_seconds）。

    曲の長さが不明なときは dj_bot_interval_seconds をフォールバックに使う。
    """
    seconds = await _duration_of(video_id)
    limit = seconds if seconds else settings.dj_bot_interval_seconds
    return max(15, min(limit, settings.dj_bot_max_seconds))


async def play_next(db: AsyncSession, station: Station) -> bool:
    """局に応じたソースから次の1曲を選んでオンエアする。"""
    src = resolve_source(station)
    pick = await random_track(
        exclude_id=station.current_youtube_id,
        source=src["source"],
        query=src["query"],
    )
    if not pick:
        return False

    set_duration(pick.get("youtube_id"), pick.get("duration"))

    station.current_youtube_id = pick["youtube_id"]
    station.playback_started_at = datetime.now()
    await db.commit()

    # 選曲ログに記録
    await record_track(db, station.id, pick["youtube_id"], title=pick.get("title"))

    started_iso = station.playback_started_at.isoformat()
    await manager.broadcast(
        station.id,
        {
            "type": "track_update",
            "youtube_video_id": pick["youtube_id"],
            "playback_started_at": started_iso,
        },
    )
    label = pick.get("title") or pick["youtube_id"]
    await manager.broadcast(
        station.id,
        {
            "type": "system",
            "content": f"🤖 DJ BOT が次の曲をオンエア: {label}",
            "listener_count": manager.channel_count(station.id),
        },
    )
    await send_to_discord(
        settings.discord_webhook_url,
        f"🤖 DJ BOT 再生中: {label} — https://youtu.be/{pick['youtube_id']}",
        "DJ BOT",
    )
    return True
