"""小さな共通ユーティリティ。"""
import re
from typing import Optional

_YOUTUBE_PATTERNS = [
    re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})"),
    re.compile(r"^([A-Za-z0-9_-]{11})$"),
]


def parse_youtube_id(value: Optional[str]) -> Optional[str]:
    """URL または生の動画ID から YouTube 動画ID（11桁）を取り出す。"""
    if not value:
        return None
    value = value.strip()
    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return None
