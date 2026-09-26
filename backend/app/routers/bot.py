"""自動DJ局（DJ BOT）の API。

station_id が自動DJ局（bot_stations に登録）なら、バックグラウンドの
_dj_bot_loop が YouTube の人気曲チャートからランダムに選曲して流し続ける。
ここでは状態取得と「次の曲へ」スキップだけを提供する。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_user
from app.models.models import BotStation, Station, User
from app.services.bot_dj import play_next, resolve_source
from app.services.trending import mark_failed

router = APIRouter(prefix="/api/stations", tags=["bot"])


class BotReportIn(BaseModel):
    video_id: Optional[str] = None


def _require_owner(station: Optional[Station], user: User) -> Station:
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="このステーションの権限がありません")
    return station


@router.get("/{station_id}/bot")
async def get_bot(station_id: int, db: AsyncSession = Depends(get_db)):
    """この局の自動DJ状態（人気曲からランダム再生）。"""
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    bot = await db.get(BotStation, station_id)
    return {
        "success": True,
        "is_bot": bot is not None,
        "interval_seconds": bot.interval_seconds if bot else settings.dj_bot_interval_seconds,
        "source": resolve_source(station)["source"] if bot else None,
        "region": settings.dj_bot_region,
    }


@router.post("/{station_id}/bot/next")
async def next_bot_track(
    station_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """今の曲を打ち切って次の曲へ。"""
    station = _require_owner(await db.get(Station, station_id), user)
    await play_next(db, station)
    return {"success": True}


@router.post("/{station_id}/bot/report")
async def report_bot_error(
    station_id: int,
    data: BotReportIn,
    db: AsyncSession = Depends(get_db),
):
    """埋め込み再生できなかった曲を報告する（ログイン不要）。

    報告された動画が「現在オンエア中の曲」と一致する場合のみ、
    その動画をブロックリストに追加して次曲へ切り替える。
    """
    station = await db.get(Station, station_id)
    if station is None or await db.get(BotStation, station_id) is None:
        raise HTTPException(status_code=404, detail="自動DJ局が見つかりません")
    if data.video_id and station.current_youtube_id == data.video_id:
        mark_failed(data.video_id)
        await play_next(db, station)
    return {"success": True}


@router.post("/{station_id}/bot/ended")
async def ended_bot_track(
    station_id: int,
    data: BotReportIn,
    db: AsyncSession = Depends(get_db),
):
    """曲が最後まで再生されたことを報告する（ログイン不要）。

    報告された動画が「現在オンエア中の曲」と一致する場合のみ次曲へ進む。
    """
    station = await db.get(Station, station_id)
    if station is None or await db.get(BotStation, station_id) is None:
        raise HTTPException(status_code=404, detail="自動DJ局が見つかりません")
    if data.video_id and station.current_youtube_id == data.video_id:
        await play_next(db, station)
    return {"success": True}
