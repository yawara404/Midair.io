"""LINE WORKS 設定チェック用スクリプト（Miaちゃん連携）。

使い方:
  cd backend && .venv/bin/python lineworks_check.py

  .env の LINE WORKS 設定を読み、
   1) access token が取得できるか
   2) Bot が参加しているチャンネル一覧（Channel ID の確認）
   3) テスト送信
  を順に試します。
"""
import asyncio

import httpx

from app.core.config import settings
from app.services import lineworks


async def main() -> None:
    print("== LINE WORKS 設定 ==")
    print("  enabled        :", settings.lineworks_enabled)
    print("  client_id      :", "set" if settings.lineworks_client_id else "EMPTY")
    print("  client_secret  :", "set" if settings.lineworks_client_secret else "EMPTY")
    print("  service_account:", "set" if settings.lineworks_service_account else "EMPTY")
    print("  private_key    :", "set" if (settings.lineworks_private_key or settings.lineworks_private_key_file) else "EMPTY")
    print("  private_key_file:", settings.lineworks_private_key_file or "EMPTY")
    print("  bot_id         :", settings.lineworks_bot_id or "EMPTY")
    print("  channel_id     :", settings.lineworks_channel_id or "EMPTY")

    if not (
        settings.lineworks_enabled
        and settings.lineworks_client_id
        and settings.lineworks_service_account
        and (settings.lineworks_private_key or settings.lineworks_private_key_file)
    ):
        print("\n!! 認証に必要な設定が不足しています（ENABLED / CLIENT_ID / SERVICE_ACCOUNT / PRIVATE_KEY）。")
        return

    print("\n== access token 取得 ==")
    token = await lineworks._get_token()
    print("  token:", "OK" if token else "FAILED（認証情報/秘密鍵を確認）")
    if not token:
        return

    print("\n== Bot のチャンネル一覧（channel_id の確認）==")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://www.worksapis.com/v1.0/bots/{settings.lineworks_bot_id}/channels",
                headers={"Authorization": f"Bearer {token}"},
            )
        print("  HTTP", r.status_code)
        print("  ", r.text[:800])
    except Exception as e:
        print("  error:", e)

    if not settings.lineworks_channel_id:
        print("\n!! CHANNEL_ID 未設定。上の一覧の channelId を .env の LINEWORKS_CHANNEL_ID に設定してください。")
        return

    print("\n== テスト送信 ==")
    ok = await lineworks.send_message("Midair.io からのテスト送信です（Miaちゃん）")
    print("  send:", "OK" if ok else "FAILED（channel_id / Bot の権限を確認）")


if __name__ == "__main__":
    asyncio.run(main())
