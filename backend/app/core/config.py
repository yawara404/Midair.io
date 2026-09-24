"""環境変数・設定。

.env（backend/.env）を読み込み、未設定の場合はデフォルト値を使う。
データベースは SQLite をデフォルトとし、DATABASE_URL を書き換えると
MySQL（asyncmy）にも切り替えられる。
"""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# このファイルは backend/app/core/config.py → backend/.env を参照する
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_name: str = "Midair.io"

    # SQLite デフォルト / MySQL は env で切替
    database_url: str = "sqlite+aiosqlite:///./midair.db"

    # 認証 / JWT
    secret_key: str = "midair-dev-secret-key-change-me-in-production-0123456789"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7日

    # 初期管理者アカウント（初回起動時のシード。.env で必ず変更する）
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-admin"

    # Discord OAuth2（設定時のみ有効）
    discord_client_id: Optional[str] = None
    discord_client_secret: Optional[str] = None
    discord_redirect_uri: Optional[str] = None
    frontend_url: str = "http://localhost:5173"

    # Discord チャット同期（Webhook URL）
    discord_webhook_url: Optional[str] = None

    # Google Gemini API（AIラジオDJ）
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.6-flash"

    # YouTube Data API（任意。曲タイトル取得などに使用）
    # ※ 埋め込み再生（IFrame Player API）にはキーは不要。
    youtube_api_key: Optional[str] = None

    # AI DJ の動作設定
    dj_enabled: bool = True
    dj_idle_seconds: int = 45

    # AIチャットbot（リスナーの発言に返信）のクールダウン秒数
    bot_reply_cooldown_seconds: int = 12

    # --- LINE WORKS 連携（Miaちゃんのチャットbot） ---
    # 双方向: Midair → LINE WORKS チャンネルへ転送 / LINE WORKS → Midair に投稿
    lineworks_enabled: bool = False
    lineworks_client_id: Optional[str] = None
    lineworks_client_secret: Optional[str] = None
    lineworks_service_account: Optional[str] = None
    # PEM秘密鍵（改行はそのまま、または \n エスケープ可）
    lineworks_private_key: Optional[str] = None
    # 秘密鍵をファイルで指定する場合（.pem/.key のパス）。上の値より優先はしません。
    lineworks_private_key_file: Optional[str] = None
    lineworks_bot_id: Optional[str] = None
    lineworks_channel_id: Optional[str] = None
    # 連携する Midair の局（コールサイン）
    lineworks_station_callsign: str = "Miaちゃん"

    # 自動DJ局（DJ BOT）— 流行りの曲からランダムに流し続ける常時オンエア局
    dj_bot_enabled: bool = True
    dj_bot_frequency: float = 84.0
    # 1曲を流す目安の秒数（曲の長さが不明なときのフォールバック）
    dj_bot_interval_seconds: int = 180
    # 1曲の最大再生秒数（これを超える長い曲は途中でスキップ／既定10分）
    dj_bot_max_seconds: int = 600
    # 人気曲チャート（YouTube mostPopular / ミュージック）の地域とキャッシュ時間
    dj_bot_region: str = "JP"
    dj_bot_trending_cache_minutes: int = 30

    # 専用局（24時間常設）の自律運行エンジン
    dedicated_engine_enabled: bool = True
    dedicated_engine_interval_seconds: int = 10

    # 開局できる周波数レンジ（MHz）
    station_freq_min: float = 76.0
    station_freq_max: float = 88.9

    # CORS 許可オリジン
    cors_origins: str = "*"

    # サブパス配信時の API ルート（例: /Midair.io）。ローカル/root 配信では空。
    root_path: str = ""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
