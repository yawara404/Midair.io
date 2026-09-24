"""自動DJ局（DJ BOT / Vocaloid BOT）の選曲ソース。

- trending: YouTube mostPopular（ミュージック）から人気曲を取得
- search:   YouTube 検索（例: ボカロ）から曲を取得

いずれも「埋め込み再生できる通常動画」だけを採用し、ランダムに1曲選ぶ。
APIキー未設定・取得失敗時は埋め込み可能な内蔵プールにフォールバックする。
"""
import random
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.services.youtube import parse_iso_duration

# APIが使えないとき用の内蔵フォールバック（埋め込み再生できることを確認済みのID）
_FALLBACK: list[tuple[str, str]] = [
    ("60ItHLz5WEA", "Alan Walker - Faded"),
    ("DeKLpgzh-qQ", "稲葉曇『ロストアンブレラ』Vo. 歌愛ユキ"),
    ("4xDzrJKXOOY", "lofi synthwave radio 🌌"),
]

# 実際に埋め込み再生できなかった動画（このプロセス内で除外する）
_failed_ids: set[str] = set()

# キャッシュ: key -> {"at": float, "items": list[dict]}
_cache: dict[str, dict] = {}


def _fallback_items() -> list[dict]:
    return [
        {"youtube_id": vid, "title": title, "duration": None}
        for vid, title in _FALLBACK
    ]


def mark_failed(video_id: Optional[str]) -> None:
    """再生できなかった動画をブロックリストに追加する。"""
    if video_id:
        _failed_ids.add(video_id)


def _filter_items(items: list[dict]) -> list[dict]:
    """埋め込み可能な通常動画だけを抽出する。"""
    out = []
    for item in items:
        video_id = item.get("id")
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        if not video_id:
            continue
        if status.get("embeddable") is False:
            continue
        if snippet.get("liveBroadcastContent") not in (None, "none"):
            continue
        if video_id in _failed_ids:
            continue
        out.append(
            {
                "youtube_id": video_id,
                "title": snippet.get("title"),
                "duration": parse_iso_duration(
                    item.get("contentDetails", {}).get("duration")
                ),
            }
        )
    return out


async def _videos_by_ids(ids: list[str]) -> list[dict]:
    """動画IDから snippet/status/contentDetails を取得してフィルタする。"""
    ids = [i for i in ids if i]
    if not ids or not settings.youtube_api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,status,contentDetails",
                    "id": ",".join(ids[:50]),
                    "maxResults": 50,
                    "key": settings.youtube_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    return _filter_items(items)


async def _fetch_trending() -> list[dict]:
    """YouTube mostPopular（ミュージック）から取得する。"""
    if not settings.youtube_api_key:
        return []
    params = {
        "part": "snippet,status,contentDetails",
        "chart": "mostPopular",
        "videoCategoryId": "10",  # Music
        "maxResults": 50,
        "key": settings.youtube_api_key,
    }
    region = (settings.dj_bot_region or "").strip()
    if region:
        params["regionCode"] = region
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    return _filter_items(items)


async def _fetch_search(query: str) -> list[dict]:
    """YouTube 検索クエリ（例: ボカロ）から取得する。"""
    if not settings.youtube_api_key or not query:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoEmbeddable": "true",
        "maxResults": 50,
        "order": "viewCount",
        "key": settings.youtube_api_key,
    }
    region = (settings.dj_bot_region or "").strip()
    if region:
        params["regionCode"] = region
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search", params=params, timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    ids = [item.get("id", {}).get("videoId") for item in items]
    # 埋め込み可否・長さをまとめて取得
    return await _videos_by_ids(ids)


def _cache_key(source: str, query: Optional[str]) -> str:
    return f"{source}:{query or ''}"


async def pool(source: str = "trending", query: Optional[str] = None) -> list[dict]:
    """選曲プール（キャッシュ付き）。取得できなければフォールバックを返す。"""
    key = _cache_key(source, query)
    ttl = max(1, settings.dj_bot_trending_cache_minutes) * 60
    now = time.time()
    entry = _cache.get(key)
    if entry and entry["items"] and now - entry["at"] < ttl:
        return entry["items"]

    items = (
        await _fetch_search(query) if source == "search" else await _fetch_trending()
    )
    if items:
        _cache[key] = {"at": now, "items": items}
        return items
    if entry and entry["items"]:
        return entry["items"]
    return _fallback_items()


async def random_track(
    exclude_id: Optional[str] = None,
    source: str = "trending",
    query: Optional[str] = None,
) -> Optional[dict]:
    """プールからランダムに1曲選ぶ（失敗済み・直前と同じ曲は避ける）。"""
    items = await pool(source, query)
    items = [x for x in items if x["youtube_id"] not in _failed_ids] or items
    if not items:
        return None
    choices = [x for x in items if x["youtube_id"] != exclude_id] or items
    return random.choice(choices)
