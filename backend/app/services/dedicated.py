"""専用局（24時間常設）の自律運行エンジン。

- 送出キュー（broadcast_queue）を最優先で消化
- キューが空なら内部音源プール（dedicated_track_library）からランダムに選曲
- 選曲を Station に反映し、WebSocket でリスナーへ同期
APScheduler により一定間隔（既定10秒）で check_and_advance() を呼ぶ。
"""
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    BroadcastQueue,
    DedicatedTrackLibrary,
    Station,
)
from app.services.sessions import record_track
from app.services.websocket_manager import manager

_DEFAULT_DURATION = 200
# 1曲の最大再生秒数（ライブ配信など極端に長い尺をクランプ）
_MAX_DURATION = 600


async def _fetch_duration(youtube_id: str) -> Optional[int]:
    """YouTube Data API で動画の長さ（秒）を取得する。"""
    if not settings.youtube_api_key or not youtube_id:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "contentDetails",
                    "id": youtube_id,
                    "key": settings.youtube_api_key,
                },
                timeout=8,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None
            from app.services.youtube import parse_iso_duration

            return parse_iso_duration(
                items[0].get("contentDetails", {}).get("duration")
            )
    except Exception:
        return None


async def resolve_track_meta(youtube_id: str, title: Optional[str] = None) -> dict:
    """動画IDからタイトル・長さを解決する（不足分を補完）。"""
    resolved_title = title
    duration = None
    if settings.youtube_api_key:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "snippet,contentDetails",
                        "id": youtube_id,
                        "key": settings.youtube_api_key,
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if items:
                    snippet = items[0].get("snippet", {})
                    resolved_title = resolved_title or snippet.get("title")
                    from app.services.youtube import parse_iso_duration

                    duration = parse_iso_duration(
                        items[0].get("contentDetails", {}).get("duration")
                    )
        except Exception:
            pass
    d = duration or _DEFAULT_DURATION
    return {
        "youtube_id": youtube_id,
        "title": resolved_title or youtube_id,
        "duration_seconds": max(30, min(d, _MAX_DURATION)),
    }


def _is_finished(station: Station, now: datetime) -> bool:
    if not station.playback_started_at or not station.current_youtube_id:
        return True
    return now >= station.playback_started_at + timedelta(
        seconds=station.track_duration_sec or _DEFAULT_DURATION
    )


async def advance_station(db: AsyncSession, station: Station, now: Optional[datetime] = None) -> bool:
    """専用局の次の曲を選んで送出する（キュー優先 → ライブラリ）。"""
    now = now or datetime.now()

    # 1. 送信キューを優先（未再生・sort_order 昇順）
    queued = (
        await db.execute(
            select(BroadcastQueue)
            .where(
                BroadcastQueue.station_id == station.id,
                BroadcastQueue.is_played.is_(False),
            )
            .order_by(BroadcastQueue.sort_order.asc(), BroadcastQueue.id.asc())
            .limit(1)
        )
    ).scalars().first()

    if queued is not None:
        queued.is_played = True
        video_id = queued.youtube_id
        title = queued.title or queued.youtube_id
        duration = queued.duration_seconds or _DEFAULT_DURATION
    else:
        # 2. ライブラリからランダムに選曲（RANDOM() は SQLite/MySQL 両対応のため全件から抽選）
        tracks = (
            await db.execute(
                select(DedicatedTrackLibrary).where(
                    DedicatedTrackLibrary.station_id == station.id
                )
            )
        ).scalars().all()
        if not tracks:
            return False
        pick = random.choice(tracks)
        video_id = pick.youtube_id
        title = pick.title or pick.youtube_id
        duration = pick.duration_seconds or _DEFAULT_DURATION

    station.current_youtube_id = video_id
    station.playback_started_at = now
    station.track_duration_sec = duration
    station.set_status("live")
    await db.commit()

    # 選曲ログに記録
    await record_track(db, station.id, video_id, title=title)

    # 3. リスナーへ即時同期
    await manager.broadcast(
        station.id,
        {
            "type": "track_update",
            "youtube_video_id": video_id,
            "playback_started_at": now.isoformat(),
        },
    )
    await manager.broadcast(
        station.id,
        {
            "type": "system",
            "content": f"📻 専用局が次の曲を送出: {title}",
            "listener_count": manager.channel_count(station.id),
        },
    )
    return True


async def check_and_advance(db: AsyncSession) -> int:
    """全専用局を走査し、曲が終わっていれば次曲へ進める。進めた局数を返す。"""
    now = datetime.now()
    stations = (
        await db.execute(select(Station).where(Station.is_dedicated.is_(True)))
    ).scalars().all()
    advanced = 0
    for station in stations:
        if _is_finished(station, now):
            if await advance_station(db, station, now):
                advanced += 1
    return advanced


async def seed_initial_library(
    db: AsyncSession, station: Station, tracks: list[dict]
) -> int:
    """承認時に申請の初期選曲リストをライブラリへ移行する。"""
    count = 0
    for t in tracks or []:
        video_id = (t or {}).get("youtube_id")
        if not video_id:
            continue
        meta = await resolve_track_meta(video_id, (t or {}).get("title"))
        db.add(
            DedicatedTrackLibrary(
                station_id=station.id,
                youtube_id=meta["youtube_id"],
                title=meta["title"],
                duration_seconds=meta["duration_seconds"],
            )
        )
        count += 1
    if count:
        await db.commit()
    return count
