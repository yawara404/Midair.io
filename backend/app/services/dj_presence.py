"""DJの滞在（自動退出）管理。

- 「DJを呼ぶ」ボタンや「DJさん」の呼びかけで DJ が**滞在**を開始する。
- 自動DJ局（DJ BOT / Vocaloid BOT / 管理者セレクト）以外のDJは、
  最後に呼ばれてから `DJ_STAY_SECONDS`（既定10分。局ごとの設定で変更可）を
  過ぎると**自動退出**して黙る（独り口を話さない）。
- 滞在状態はプロセス内で保持する（バックエンド再起動で全DJが退出状態に戻る）。
"""
import time
from typing import Optional

from app.core.config import settings
from app.models.models import Station

# 局ID -> 最後に呼ばれた時刻（epoch秒）
_last_called: dict[int, float] = {}


def mark_called(station_id: int) -> None:
    """DJが呼ばれた（＝滞在開始／延長）ことを記録する。"""
    _last_called[station_id] = time.time()


def last_called(station_id: int) -> Optional[float]:
    return _last_called.get(station_id)


def forget(station_id: int) -> None:
    _last_called.pop(station_id, None)


def stay_seconds(station: Optional[Station]) -> int:
    """この局のDJ滞在秒数（0 なら退出しない＝常時おしゃべり）。"""
    minutes = station.dj_stay_minutes if station is not None else None
    if minutes is None:
        return max(0, int(settings.dj_stay_seconds))
    return max(0, int(minutes) * 60)


def is_present(station_id: int, station: Optional[Station] = None) -> bool:
    """DJが滞在中か（呼ばれてから滞在時間内か）。"""
    limit = stay_seconds(station)
    if limit <= 0:
        # 退出しない設定（従来どおり常時おしゃべり）
        return True
    called = _last_called.get(station_id)
    if called is None:
        return False
    return (time.time() - called) < limit


def remaining_seconds(station_id: int, station: Optional[Station] = None) -> int:
    """退出までの残り秒数（退出しない設定なら 0）。"""
    limit = stay_seconds(station)
    if limit <= 0:
        return 0
    called = _last_called.get(station_id)
    if called is None:
        return 0
    return max(0, int(limit - (time.time() - called)))
