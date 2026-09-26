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

    # LLM プロバイダ選択: auto | gemini | openai
    # auto は openai_api_key があれば openai、無ければ gemini を使う。
    llm_provider: str = "auto"

    # Google Gemini API（AIラジオDJ）
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.6-flash"

    # OpenAI 互換 API（OpenRouter / Groq / OpenAI / ローカル Ollama など）
    # base_url を変えるだけで各種サービスに対応（例:
    #   OpenRouter: https://openrouter.ai/api/v1
    #   Groq:       https://api.groq.com/openai/v1
    #   Ollama:     http://localhost:11434/v1  (api_key は任意の文字列)
    #   OpenAI:     https://api.openai.com/v1
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # 生成パラメータ（自由思考のまま、暴走・文字化けを抑える）
    llm_temperature: float = 0.8
    llm_max_tokens: int = 300

    # YouTube Data API（任意。曲タイトル取得などに使用）
    # ※ 埋め込み再生（IFrame Player API）にはキーは不要。
    youtube_api_key: Optional[str] = None

    # DJ の動作設定
    dj_enabled: bool = True
    dj_idle_seconds: int = 120
    # DJは「DJさん」「hey DJ」と呼びかけられたときだけ返事する
    # （Discord連携局のMiaちゃんはチャットbotなので常時返事する。
    #   False にすると従来どおり全てのチャットに返事する）
    dj_reply_requires_call: bool = True

    # --- 今オンエア中の曲に連動したDJコメント ---
    # アイドルDJ・「DJを呼ぶ」・チャット返信のコメントに、今流れている曲名を渡して
    # 曲の話題（印象・歌詞・聴きどころ）に触れさせる。
    dj_track_comment_enabled: bool = True
    # 曲が切り替わった瞬間にDJが曲紹介コメントを投稿する
    # （既定 off。DJは「独り口」（無言が続いたときのひとこと）で曲に連動します。
    #   true にすると曲切替のたびに曲紹介も投稿します）
    dj_track_intro_enabled: bool = False
    # 同じ局で曲紹介を連投しないための最小間隔（秒）
    dj_track_intro_cooldown_seconds: int = 10
    # 誰も聴いていない局では曲紹介をしない（LLM呼び出しの節約）
    dj_track_intro_requires_listener: bool = True

    # AIチャットbot（リスナーの発言に返信）のクールダウン秒数
    bot_reply_cooldown_seconds: int = 12

    # --- Discord 連携（Miaちゃんのチャットbot・双方向 / discord.py Gateway） ---
    # Midair → Discord チャンネルへ転送 / Discord チャンネル → Midair に投稿
    discord_bot_enabled: bool = False
    discord_bot_token: Optional[str] = None
    # 連携する Discord のチャンネルID（テキストチャンネル）
    discord_channel_id: Optional[str] = None
    # 連携する Midair の局（コールサイン）
    discord_station_callsign: str = "Miaちゃん"

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
    # 直近何曲を重複回避するか（自動DJ局の全ソース共通）
    dj_bot_recent_exclude: int = 30
    # これ以下の再生数の動画は選曲しない（0 で無効）
    dj_bot_min_views: int = 1000
    # 人気曲の優先度（0=完全ランダム / 0.5=控えめに人気曲を優先 / 1.0=再生数に比例）
    dj_bot_popularity_power: float = 0.5

    # --- Vocaloid BOT（85.0MHz）---
    # 歌声・ジャンル・年代・プロデューサー別の検索テーマを巡回して候補を蓄積する。
    # 1回のリフレッシュで引くテーマ数（ファミリーをまたいで選ぶ）
    dj_bot_vocaloid_themes_per_refresh: int = 3
    # テーマを入れ替える間隔（分）。候補プールは保持されたまま少しずつ更新される。
    dj_bot_vocaloid_cache_minutes: int = 90
    # 蓄積する候補プールの上限（この中から直近の曲と重複しない曲をランダムに選ぶ）
    dj_bot_vocaloid_pool_size: int = 400
    # 合成音声歌唱優先: 歌声合成（ボカロ等）のクレジットが確認できる曲だけを流す。
    #   True  = タイトル/タグ/説明欄/投稿者名のどこかにクレジットが必要
    #           （人が歌っている曲・インストを流さない）
    #   False = 投稿者（ボカロP・公式チャンネル）だけで判断する従来動作
    dj_bot_vocaloid_synth_only: bool = True
    # タイトルに歌声合成のクレジットがある曲（＝合成音声の歌唱とほぼ確実）を
    # どれだけ優先するか。選曲の重みに (1 + この値) を掛ける
    # （0=優先しない / 1.0=2倍 / 3.0=4倍。人気曲の重みに上乗せされる）
    dj_bot_vocaloid_synth_bias: float = 1.0
    # 新曲（最近公開された曲）をどれだけ優先するか。
    # dj_bot_vocaloid_fresh_days 以内に公開された曲の重みを (1 + この値) 倍する
    # （0=優先しない / 0.6=1.6倍。控えめに後押しする程度にしておく）
    dj_bot_vocaloid_fresh_bias: float = 0.6
    # 「新曲」とみなす日数（この日数以内は上の倍率、3倍の日数以内は半分の倍率）
    dj_bot_vocaloid_fresh_days: int = 30

    # 専用局（24時間常設）の自律運行エンジン
    dedicated_engine_enabled: bool = True
    dedicated_engine_interval_seconds: int = 10

    # 開局できる周波数レンジ（MHz）
    station_freq_min: float = 76.0
    station_freq_max: float = 88.9

    # --- 周波数帯の区分（総スロット数は増やさない） ---
    # 専用局（24時間常設・申請承認制）を開設できる帯。
    # この帯の外は「自由な周波数」＝誰でも自由に開局・時間枠予約できる一般帯として扱う。
    # （既定: 76.0〜79.9MHz＝専用局帯 / 80.0〜88.9MHz＝自由な周波数）
    dedicated_freq_min: float = 76.0
    dedicated_freq_max: float = 79.9

    # --- 切り忘れ対策（放送の停波忘れ防止） ---
    # ON AIR からこの分数が過ぎたら自動停波する（0 = 無効）
    auto_off_after_minutes: int = 360
    # 無人（リスナー0人・チャットなし）のままこの分数が過ぎたら自動停波（0 = 無効）
    auto_off_idle_minutes: int = 120
    # 自動停波の何分前に放送内で告知するか（0 = 告知なし）
    auto_off_notice_minutes: int = 5

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
