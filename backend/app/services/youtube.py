"""YouTube API ヘルパー。

- 再生（埋め込み）にはキーは不要（IFrame Player API）。
- 動画情報（タイトル・埋め込み可否）は `YOUTUBE_API_KEY` があれば
  YouTube Data API v3 を使用し、未設定時は oEmbed にフォールバックする。
"""
import re
from typing import Optional

import httpx

from app.core.config import settings

_ISO_DURATION_RE = re.compile(
    r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
)


def parse_iso_duration(value: Optional[str]) -> Optional[int]:
    """ISO 8601 の動画時間（例: PT4M13S）を秒に変換する。"""
    if not value:
        return None
    match = _ISO_DURATION_RE.match(value)
    if not match:
        return None
    days, hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total or None


async def fetch_video_duration(video_id: str) -> Optional[int]:
    """YouTube Data API で動画の長さ（秒）を取得する（キー未設定時は None）。"""
    if not settings.youtube_api_key or not video_id:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "contentDetails",
                    "id": video_id,
                    "key": settings.youtube_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None
            return parse_iso_duration(
                items[0].get("contentDetails", {}).get("duration")
            )
    except Exception:
        return None


async def fetch_video_info(video_id: str) -> dict:
    """動画情報 {title, embeddable, found} を取得する。

    YOUTUBE_API_KEY があれば Data API、なければ oEmbed を使う。
    """
    if settings.youtube_api_key:
        info = await _fetch_via_data_api(video_id)
        if info is not None:
            return info
    return await _fetch_via_oembed(video_id)


async def _fetch_via_data_api(video_id: str) -> Optional[dict]:
    """YouTube Data API v3 で動画情報を取得する（キー設定時）。"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,status",
                    "id": video_id,
                    "key": settings.youtube_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return {"title": None, "embeddable": False, "found": False}
            item = items[0]
            return {
                "title": item.get("snippet", {}).get("title"),
                "embeddable": bool(item.get("status", {}).get("embeddable", True)),
                "found": True,
            }
    except Exception:
        return None


async def _fetch_via_oembed(video_id: str) -> dict:
    """oEmbed で動画情報を取得する（キー未設定時のフォールバック）。"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": f"https://youtu.be/{video_id}", "format": "json"},
                timeout=10,
            )
            if resp.status_code == 200:
                return {
                    "title": resp.json().get("title"),
                    "embeddable": True,
                    "found": True,
                }
            return {
                "title": None,
                "embeddable": False,
                "found": resp.status_code != 404,
            }
    except Exception:
        # 判定できない場合は通す
        return {"title": None, "embeddable": True, "found": True}


async def check_embeddable(video_id: str) -> bool:
    """埋め込み再生が可能かを返す。"""
    info = await fetch_video_info(video_id)
    return bool(info.get("embeddable", True))


async def fetch_youtube_title(video_id: str) -> Optional[str]:
    """動画タイトルを取得する。"""
    info = await fetch_video_info(video_id)
    return info.get("title")
