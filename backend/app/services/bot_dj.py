"""自動DJ局（DJ BOT / Vocaloid BOT）の選曲・再生ロジック。

- 曲が終わったら次の曲へ（曲の長さを基に判定）
- 長すぎる曲は dj_bot_max_seconds（既定10分）で途中スキップ
- 直近に流した曲（dj_bot_recent_exclude 曲）は選曲から外して重複を防ぐ
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import BroadcastSession, SessionTrack, Station
from app.services.discord_sync import send_to_discord
from app.services.sessions import record_track
from app.services.trending import random_track
from app.services.websocket_manager import manager
from app.services.youtube import fetch_video_duration

# 局名 -> 選曲ソース設定（callsign で判定）
BOT_SOURCES: dict[str, dict] = {
    "DJ BOT": {"source": "trending", "query": None},
    "Vocaloid BOT": {"source": "vocaloid", "query": None},
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


async def _recent_track_ids(
    db: AsyncSession, station_id: int, limit: int
) -> list[str]:
    """直近の選曲履歴から、重複回避に使う動画IDを集める。"""
    if limit <= 0:
        return []
    result = await db.execute(
        select(SessionTrack.youtube_id)
        .join(BroadcastSession, SessionTrack.session_id == BroadcastSession.id)
        .where(BroadcastSession.station_id == station_id)
        .order_by(SessionTrack.id.desc())
        .limit(limit)
    )
    return [video_id for video_id in result.scalars() if video_id]


async def play_next(db: AsyncSession, station: Station) -> bool:
    """局に応じたソースから次の1曲を選んでオンエアする。"""
    src = resolve_source(station)
    # 直近に流した曲は避けて選曲する（同じ曲・同じ並びの繰り返しを防ぐ）
    recent_ids = await _recent_track_ids(
        db, station.id, settings.dj_bot_recent_exclude
    )
    pick = await random_track(
        exclude_id=station.current_youtube_id,
        exclude_ids=recent_ids,
        source=src["source"],
        query=src["query"],
    )
    if not pick:
        return False

    set_duration(pick.get("youtube_id"), pick.get("duration"))

    station.current_youtube_id = pick["youtube_id"]
    station.playback_started_at = datetime.now()
    await db.commit()

    # 選曲ログに記録（再生ログを即時更新できるよう WS にも載せる）
    track = await record_track(
        db, station.id, pick["youtube_id"], title=pick.get("title")
    )

    started_iso = station.playback_started_at.isoformat()
    await manager.broadcast(
        station.id,
        {
            "type": "track_update",
            "youtube_video_id": pick["youtube_id"],
            "playback_started_at": started_iso,
            "track": track.to_dict() if track else None,
        },
    )
    label = pick.get("title") or pick["youtube_id"]
    # 局名（DJ BOT / Vocaloid BOT）で告知して、どちらの局の曲かわかるようにする
    await manager.broadcast(
        station.id,
        {
            "type": "system",
            "content": f"🤖 {station.callsign} が次の曲をオンエア: {label}",
            "listener_count": manager.channel_count(station.id),
        },
    )
    await send_to_discord(
        settings.discord_webhook_url,
        f"🤖 {station.callsign} 再生中: {label} — https://youtu.be/{pick['youtube_id']}",
        station.callsign,
    )
    return True
