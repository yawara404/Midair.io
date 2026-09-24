"""Discord 双方向連携（Miaちゃん）。

- Midair の対象局（既定: Miaちゃん）の発言 → Discord の指定チャンネルへ転送
- Discord の指定チャンネルの発言 → Midair の対象局へ投稿し、さらに Mia として
  LLM の返信を生成して Discord と Midair の両方へ投稿する。

discord.py の Gateway（WebSocket）接続を使うため、常時接続のBotとして動作する。
必要な設定（backend/.env）:
  DISCORD_BOT_ENABLED=true
  DISCORD_BOT_TOKEN=（Botトークン）
  DISCORD_CHANNEL_ID=（連携するテキストチャンネルのID）
  DISCORD_STATION_CALLSIGN=Miaちゃん   # 連携する Midair の局

注意:
- Discord Developer Portal の Bot 設定で「MESSAGE CONTENT INTENT」を ON にすること。
- Bot をサーバーへ招待し、対象チャンネルへの送信権限を与えること。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.config import settings

_client = None
_task: Optional[asyncio.Task] = None
_ready = asyncio.Event()


def is_configured() -> bool:
    """Discord 連携に必要な設定が揃っているか。"""
    return bool(
        settings.discord_bot_enabled
        and settings.discord_bot_token
        and settings.discord_channel_id
    )


async def _get_station():
    """連携対象の Midair 局を取得する。"""
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.models import Station

    async with async_session_factory() as session:
        station = (
            await session.execute(
                select(Station).where(
                    Station.callsign == settings.discord_station_callsign
                )
            )
        ).scalars().first()
        return station


async def _handle_discord_message(name: str, content: str) -> None:
    """Discord の発言を Midair へ投稿し、Mia の返信を両方へ投稿する。"""
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.models import Message
    from app.routers.ws import _persist_message
    from app.services.websocket_manager import manager

    station = await _get_station()
    if station is None:
        return
    station_id = station.id
    callsign = station.callsign
    persona = station.ai_dj_prompt

    # 1) Discord の発言を Midair へ（発言者名で）
    payload = await _persist_message(station_id, name, content[:500])
    await manager.broadcast(station_id, {"type": "message", **payload})
    manager.touch(station_id)

    # 2) Mia として LLM 返信を生成し、Discord と Midair の両方へ投稿
    try:
        from app.services.ai_dj import maybe_chat_reply

        context = ""
        async with async_session_factory() as cs:
            rows = (
                await cs.execute(
                    select(Message)
                    .where(Message.station_id == station_id)
                    .order_by(Message.id.desc())
                    .limit(6)
                )
            ).scalars().all()
            context = "\n".join(
                f"{m.sender_name}: {m.content}" for m in reversed(rows)
            )
        reply = await maybe_chat_reply(
            station_id, callsign, persona, True, content, context=context
        )
        if reply:
            await send_message(reply)
            rp = await _persist_message(station_id, "Mia", reply, is_dj=True)
            await manager.broadcast(station_id, {"type": "message", **rp})
    except Exception as e:  # pragma: no cover
        print("[discord] reply error:", e)


def _build_client():
    import discord

    intents = discord.Intents.default()
    # メッセージ本文を読むには特権インテントが必要（Portal で ON）
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():  # noqa: ANN001
        _ready.set()
        print(f"[discord] logged in as {client.user}")

    @client.event
    async def on_message(message):  # noqa: ANN001
        try:
            if message.author.bot:
                return
            if str(message.channel.id) != str(settings.discord_channel_id):
                return
            content = (message.content or "").strip()
            if not content:
                return
            name = getattr(message.author, "display_name", None) or message.author.name
            await _handle_discord_message(name, content)
        except Exception as e:  # pragma: no cover
            print("[discord] relay error:", e)

    return client


async def _run() -> None:
    try:
        await _client.start(settings.discord_bot_token)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # pragma: no cover
        print("[discord] 接続エラー:", e)


async def start() -> None:
    """Bot をバックグラウンドタスクとして起動する（設定時のみ）。"""
    global _client, _task
    if not is_configured():
        return
    try:
        import discord  # noqa: F401
    except Exception as e:
        print("[discord] discord.py が未インストールのため連携を無効化:", e)
        return
    if _task is not None:
        return
    _client = _build_client()
    _task = asyncio.create_task(_run())
    print(f"[discord] starting bot (channel={settings.discord_channel_id})")


async def stop() -> None:
    """Bot を停止する。"""
    global _client, _task
    if _client is not None:
        try:
            await _client.close()
        except (Exception, asyncio.CancelledError):
            pass
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (Exception, asyncio.CancelledError):
            pass
    _client = None
    _task = None


async def send_message(text: str) -> bool:
    """Discord の対象チャンネルへテキストを送信する。"""
    if not text or _client is None or not _ready.is_set():
        return False
    try:
        channel = _client.get_channel(int(settings.discord_channel_id))
        if channel is None:
            channel = await _client.fetch_channel(int(settings.discord_channel_id))
        if channel is None:
            return False
        await channel.send(text[:1900])
        return True
    except Exception as e:  # pragma: no cover
        print("[discord] send error:", e)
        return False
