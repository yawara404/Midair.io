"""LINE WORKS コールバック（LINE WORKS → Midair）。

LINE WORKS の Bot に設定したコールバックURL宛に届くイベントを処理し、
チャンネルへの投稿テキストを Midair の該当局（既定: Miaちゃん）へ
「Mia」として投稿する。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Station
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api", tags=["lineworks"])


def _extract_text(event: dict) -> str:
    content = event.get("content")
    if isinstance(content, dict):
        if content.get("type") in (None, "text"):
            return (content.get("text") or "").strip()
    # 互換: message.text 形式
    message = event.get("message")
    if isinstance(message, dict):
        return (message.get("text") or "").strip()
    return ""


@router.post("/lineworks/callback")
async def lineworks_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """LINE WORKS からのイベントを受け取り、Midair へ投稿する。"""
    try:
        body = await request.json()
    except Exception:
        return {"success": False, "error": "invalid json"}

    events = body if isinstance(body, list) else [body]
    posted = 0

    station = (
        await db.execute(
            select(Station).where(
                Station.callsign == settings.lineworks_station_callsign
            )
        )
    ).scalars().first()
    if station is None:
        return {"success": False, "error": "station not found"}

    from app.routers.ws import _persist_message

    for event in events:
        if not isinstance(event, dict):
            continue
        if (event.get("type") or "").lower() != "message":
            continue
        text = _extract_text(event)
        if not text:
            continue
        payload = await _persist_message(
            station.id, "Mia", text[:500], is_dj=True
        )
        await manager.broadcast(station.id, {"type": "message", **payload})
        posted += 1

    return {"success": True, "posted": posted}
