"""LINE WORKS Bot API 連携（Miaちゃんのチャットbot）。

双方向:
- Midair のチャット発言 → LINE WORKS のチャンネルへ転送（send_message）
- LINE WORKS のチャンネル投稿 → Midair のチャットへ投稿（routers/lineworks.py のコールバック）

認証は Service Account（JWTアサーション）で access token を取得する。
必要な設定（backend/.env）:
  LINEWORKS_ENABLED=true
  LINEWORKS_CLIENT_ID / LINEWORKS_CLIENT_SECRET
  LINEWORKS_SERVICE_ACCOUNT
  LINEWORKS_PRIVATE_KEY   # PEM（改行は \\n エスケープ可）
  LINEWORKS_BOT_ID / LINEWORKS_CHANNEL_ID
"""
import time
from typing import Optional

import httpx
import jwt

from app.core.config import settings

_TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
_API_BASE = "https://www.worksapis.com/v1.0"

_token: dict = {"value": None, "exp": 0.0}


def _private_key() -> Optional[str]:
    # ファイル指定が優先（PEM をそのまま読む）
    if settings.lineworks_private_key_file:
        try:
            with open(settings.lineworks_private_key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    key = settings.lineworks_private_key
    if not key:
        return None
    # .env で \n エスケープされている場合に対応
    return key.replace("\\n", "\n")


def is_configured() -> bool:
    return bool(
        settings.lineworks_enabled
        and settings.lineworks_client_id
        and settings.lineworks_service_account
        and (settings.lineworks_private_key or settings.lineworks_private_key_file)
        and settings.lineworks_bot_id
        and settings.lineworks_channel_id
    )


async def _get_token() -> Optional[str]:
    """Service Account の JWT アサーションで access token を取得する（キャッシュ）。"""
    now = time.time()
    if _token["value"] and now < _token["exp"] - 60:
        return _token["value"]
    if not is_configured():
        return None

    iat = int(now)
    assertion = jwt.encode(
        {
            "iss": settings.lineworks_client_id,
            "sub": settings.lineworks_service_account,
            "iat": iat,
            "exp": iat + 3600,
        },
        _private_key(),
        algorithm="RS256",
    )
    data = {
        "assertion": assertion,
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "scope": "bot",
    }
    if settings.lineworks_client_secret:
        data["client_id"] = settings.lineworks_client_id
        data["client_secret"] = settings.lineworks_client_secret
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(_TOKEN_URL, data=data, timeout=15)
            resp.raise_for_status()
            body = resp.json()
        _token["value"] = body["access_token"]
        _token["exp"] = now + int(body.get("expires_in", 3600))
        return _token["value"]
    except Exception:
        return None


async def send_message(text: str) -> bool:
    """LINE WORKS のチャンネルへテキストを送信する。"""
    token = await _get_token()
    if not token or not text:
        return False
    url = (
        f"{_API_BASE}/bots/{settings.lineworks_bot_id}"
        f"/channels/{settings.lineworks_channel_id}/messages"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"content": {"type": "text", "text": text[:1000]}},
                timeout=15,
            )
            return resp.status_code < 300
    except Exception:
        return False
