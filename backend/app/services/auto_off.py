"""切り忘れ対策（放送の停波忘れ防止）。

ON AIR したまま放置された局を自動で停波する。対象は次のいずれか:

- ON AIR（放送開始）から `auto_off_after_minutes` を超えた局
- 無人（リスナー0人・チャットなし）のまま `auto_off_idle_minutes` を超えた局

対象外: 自動DJ局（DJ BOT / Vocaloid BOT）・Discord連携局（Miaちゃん）・専用局
（24時間常設）・番組枠（タイムテーブル）で放送中の局・終了予定
（scheduled_end）付きの局。

停波の `auto_off_notice_minutes` 分前には放送内で告知する（押し忘れの気づき）。
`main._lifecycle_loop`（既定15秒間隔）から呼ばれる。
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import BotStation, Message, Program, Station
from app.routers.frequencies import broadcast_frequency_status
from app.services.sessions import clear_now_playing, close_session, get_open_session
from app.services.websocket_manager import manager

# 局ごとの告知済みセッション（同じ放送で二重に告知しない）
_notified: dict[int, int] = {}


def _now() -> datetime:
    return datetime.now()


def _minutes_text(minutes: int) -> str:
    """分数を「6時間」「30分」のように表記する。"""
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes // 60}時間"
    return f"{minutes}分"


async def _bot_station_ids(db: AsyncSession) -> set[int]:
    """自動DJ局（プリセット）の局ID。切り忘れ対策の対象外。"""
    return set((await db.execute(select(BotStation.station_id))).scalars().all())


async def _last_message_at(
    db: AsyncSession, station_id: int, fallback: datetime
) -> datetime:
    """その局の最後のチャット時刻（無ければ fallback）。"""
    row = (
        await db.execute(
            select(Message.created_at)
            .where(Message.station_id == station_id)
            .order_by(Message.id.desc())
            .limit(1)
        )
    ).scalars().first()
    return row or fallback


async def _has_active_program(db: AsyncSession, station_id: int, now: datetime) -> bool:
    """番組枠（タイムテーブル）で放送中か。"""
    row = (
        await db.execute(
            select(Program.id)
            .where(
                Program.station_id == station_id,
                Program.start_time <= now,
                Program.end_time > now,
            )
            .limit(1)
        )
    ).scalars().first()
    return row is not None


async def _maybe_notice(
    station: Station,
    session_id: int,
    remaining: Optional[float],
    listeners: int,
) -> None:
    """自動停波の予告を放送内へ流す（1放送につき1回）。"""
    notice = settings.auto_off_notice_minutes
    if notice <= 0 or remaining is None:
        return
    if not (0 < remaining <= notice * 60):
        return
    if _notified.get(station.id) == session_id:
        return
    _notified[station.id] = session_id
    minutes = max(1, int(round(remaining / 60)))
    await manager.broadcast(
        station.id,
        {
            "type": "system",
            "content": (
                f"⏱ 切り忘れ対策: この放送は ON AIR から"
                f"{_minutes_text(settings.auto_off_after_minutes)}で自動停波します"
                f"（残り約{minutes}分）。続ける場合はもう一度 ON AIR してください。"
            ),
            "listener_count": listeners,
        },
    )



async def check_auto_off(db: AsyncSession) -> int:
    """放置された ON AIR 局を自動停波する（停波した局数を返す）。"""
    if settings.auto_off_after_minutes <= 0 and settings.auto_off_idle_minutes <= 0:
        return 0

    now = _now()
    stations = (
        await db.execute(select(Station).where(Station.status == "live"))
    ).scalars().all()
    if not stations:
        return 0

    bot_ids = await _bot_station_ids(db)
    stopped = 0

    for station in stations:
        # 常設局（専用局・自動DJ局）と外部連携局は放置されても停波しない
        if station.is_dedicated or station.id in bot_ids:
            continue
        if station.callsign == settings.discord_station_callsign:
            continue
        # 終了予定のある放送は、その予定（ライフサイクル）に任せる
        if station.scheduled_end is not None:
            continue
        # 番組枠で放送中の局はタイムテーブルに任せる
        if await _has_active_program(db, station.id, now):
            continue

        session = await get_open_session(db, station.id)
        started_at = (
            (session.started_at if session else None)
            or station.playback_started_at
            or station.created_at
        )
        if started_at is None:
            continue

        listeners = manager.channel_count(station.id)
        reasons: list[str] = []

        # 1) ON AIR からの経過時間（押し忘れそのもの）
        remaining: Optional[float] = None
        if settings.auto_off_after_minutes > 0:
            remaining = (
                started_at + timedelta(minutes=settings.auto_off_after_minutes) - now
            ).total_seconds()
            if remaining <= 0:
                reasons.append(
                    f"ON AIR から{_minutes_text(settings.auto_off_after_minutes)}経過"
                )

        # 2) 無人（リスナー0人・チャットなし）の放置
        if settings.auto_off_idle_minutes > 0 and listeners == 0:
            last_message = await _last_message_at(db, station.id, started_at)
            if (
                last_message + timedelta(minutes=settings.auto_off_idle_minutes) - now
            ).total_seconds() <= 0:
                reasons.append(
                    f"無人（リスナー0人）のまま"
                    f"{_minutes_text(settings.auto_off_idle_minutes)}経過"
                )

        if not reasons:
            await _maybe_notice(
                station, session.id if session else 0, remaining, listeners
            )
            continue

        # 自動停波（周波数スロットは保持したまま OFF AIR にする）
        station.set_status("off_air")
        await close_session(db, station.id)
        await db.commit()
        # 砂嵐の画面の裏で最後の曲が鳴り続けないよう、今オンエア中の曲も消す
        await clear_now_playing(db, station)
        _notified.pop(station.id, None)
        await broadcast_frequency_status(station.frequency, "off_air", station.id)
        await manager.broadcast(
            station.id, {"type": "live_update", "is_live": False, "status": "off_air"}
        )
        await manager.broadcast(
            station.id,
            {
                "type": "system",
                "content": (
                    f"⏱ 切り忘れ対策で自動停波しました（{'／'.join(reasons)}）。"
                    "再開するには ON AIR を押してください。"
                ),
                "listener_count": listeners,
            },
        )
        stopped += 1

    return stopped

