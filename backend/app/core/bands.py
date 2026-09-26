"""周波数帯の区分（専用局帯 / 自由な周波数帯）。

総スロット数（station_freq_min〜station_freq_max）は増やさずに、
- 専用局（24時間常設・申請承認制）を開設できる帯
- 自由な周波数（誰でも自由に開局・時間枠予約できる一般帯）
に分けて扱う。境界は .env（DEDICATED_FREQ_MIN / DEDICATED_FREQ_MAX）で変更できる。
"""

from fastapi import HTTPException

from app.core.config import settings

BAND_DEDICATED = "dedicated"
BAND_FREE = "free"


def _round(value: float) -> float:
    return round(float(value), 1)


def _slots(lo: float, hi: float) -> list[float]:
    """lo〜hi の 0.1MHz 刻みスロット。"""
    out: list[float] = []
    freq = lo
    while freq <= hi + 1e-9:
        out.append(_round(freq))
        freq = _round(freq + 0.1)
    return out


def all_frequencies() -> list[float]:
    """全体レンジの全スロット。"""
    return _slots(_round(settings.station_freq_min), _round(settings.station_freq_max))


def dedicated_band() -> tuple[float, float]:
    """専用局帯の (下限, 上限)。全体レンジ内にクランプする。"""
    lo = _round(settings.dedicated_freq_min)
    hi = _round(settings.dedicated_freq_max)
    if hi < lo:
        lo, hi = hi, lo
    low, high = _round(settings.station_freq_min), _round(settings.station_freq_max)
    return max(lo, low), min(hi, high)


def dedicated_frequencies() -> list[float]:
    """専用局を作成できる周波数（専用局帯）。"""
    lo, hi = dedicated_band()
    return _slots(lo, hi)


def free_ranges() -> list[tuple[float, float]]:
    """自由な周波数（専用局帯を除いた残り）の範囲。上下に分かれることがある。"""
    low, high = _round(settings.station_freq_min), _round(settings.station_freq_max)
    lo, hi = dedicated_band()
    ranges: list[tuple[float, float]] = []
    if lo > low + 1e-9:
        ranges.append((low, _round(lo - 0.1)))
    if hi < high - 1e-9:
        ranges.append((_round(hi + 0.1), high))
    return ranges


def free_frequencies() -> list[float]:
    """自由な周波数（一般開局・時間枠予約ができる周波数）。"""
    out: list[float] = []
    for lo, hi in free_ranges():
        out.extend(_slots(lo, hi))
    return out


def is_dedicated_frequency(frequency: float) -> bool:
    """専用局帯の周波数か。"""
    lo, hi = dedicated_band()
    return lo - 1e-9 <= _round(frequency) <= hi + 1e-9


def band_of(frequency: float) -> str:
    """周波数の所属帯（dedicated / free）。"""
    return BAND_DEDICATED if is_dedicated_frequency(frequency) else BAND_FREE


def dedicated_range_text() -> str:
    lo, hi = dedicated_band()
    return f"{lo:.1f}〜{hi:.1f}MHz"


def free_range_text() -> str:
    ranges = free_ranges()
    if not ranges:
        return "（なし）"
    return " と ".join(f"{lo:.1f}〜{hi:.1f}MHz" for lo, hi in ranges)


def validate_range(frequency: float) -> float:
    """全体レンジ内か検証して 0.1MHz に丸めた値を返す。"""
    freq = _round(frequency)
    low, high = _round(settings.station_freq_min), _round(settings.station_freq_max)
    if freq < low or freq > high:
        raise HTTPException(
            status_code=400,
            detail=f"周波数は{low:.1f}〜{high:.1f}MHzの範囲で指定してください",
        )
    return freq


def validate_free_frequency(frequency: float) -> float:
    """自由な周波数（一般開局・時間枠予約）として妥当か検証する。"""
    freq = validate_range(frequency)
    if is_dedicated_frequency(freq):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{dedicated_range_text()}は専用局（24時間常設）専用の周波数です。"
                f"一般の開局・予約は{free_range_text()}から選んでください"
            ),
        )
    return freq


def validate_dedicated_frequency(frequency: float) -> float:
    """専用局の申請先として妥当か検証する。"""
    freq = validate_range(frequency)
    if not is_dedicated_frequency(freq):
        raise HTTPException(
            status_code=400,
            detail=(
                f"専用局は専用局帯（{dedicated_range_text()}）からのみ申請できます。"
                f"{free_range_text()}は自由な周波数（一般開局・予約）です"
            ),
        )
    return freq


def bands_payload() -> dict:
    """周波数帯の区分と切り忘れ対策の設定（フロント表示用）。"""
    bands: list[dict] = []
    lo, hi = dedicated_band()
    bands.append(
        {
            "key": BAND_DEDICATED,
            "label": "専用局（24時間常設）",
            "description": "申請承認制の常設局。申請はこの帯域からのみ。自動停波の対象外です。",
            "min": lo,
            "max": hi,
            "dedicated": True,
            "count": len(dedicated_frequencies()),
        }
    )
    for rlo, rhi in free_ranges():
        bands.append(
            {
                "key": BAND_FREE,
                "label": "自由な周波数（一般開局・時間枠予約）",
                "description": "誰でも自由に開局・予約できる一般帯域。専用局は作成できません。",
                "min": rlo,
                "max": rhi,
                "dedicated": False,
                "count": len(_slots(rlo, rhi)),
            }
        )
    return {
        "min": _round(settings.station_freq_min),
        "max": _round(settings.station_freq_max),
        "count": len(all_frequencies()),
        "bands": bands,
        "auto_off": {
            "after_minutes": settings.auto_off_after_minutes,
            "idle_minutes": settings.auto_off_idle_minutes,
            "notice_minutes": settings.auto_off_notice_minutes,
        },
    }

