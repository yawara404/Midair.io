"""Discord 連携（Webhook 送信: MidAir → Discord）。

受信側（Discord → MidAir）は、Discord 側の Webhook 送信先として
POST /api/discord/ingest を設定することで双方向同期できる。
"""
from typing import Optional

import httpx


async def send_to_discord(webhook_url: Optional[str], content: str, username: str) -> bool:
    """Discord の Webhook URL へメッセージを投稿する。"""
    if not webhook_url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url,
                json={"content": content, "username": username},
                timeout=10,
            )
            return resp.status_code < 300
    except Exception:
        return False
