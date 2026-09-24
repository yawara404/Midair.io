# Midair.io（ミッドエア）

> 周波数をダイヤルで合わせて各チャンネル（番組）に入る、24時間リアルタイム匿名BBS。
> リスナーは「名無し」で聴き、やがて自分で周波数を取得して**開局（パーソナリティ）**へステップアップできる、ミニFM放送局システムです。

## 🌟 主な機能

### リアルタイム放送
- **周波数チューナーUI** — ロータリーダイヤル／スライダーで周波数（76.0〜94.9MHz）を切り替えてステーション移動。
- **リアルタイム匿名チャット** — WebSocketによる低遅延メッセージ送受信。未ログインは「名無しのリスナー」として参加。
- **YouTube BGM同期** — ステーションごとの楽曲をリスナー全員で同時再生。
- **再生ログ** — ステーション画面（掲示板）の NOW PLAYING 欄に、その局で流れた曲の履歴を表示（`GET /api/stations/{id}/tracks`）。
- **AIラジオDJ Bot** — 会話が途切れた際や「DJを呼ぶ」に応じて自動応答（Gemini API。未設定時はルールベース）。
- **自動DJ局（プリセット局）** — 24時間オンエアで**完全ランダムに選曲**し続ける、Discordの音楽Bot的な局。
  - **「DJ BOT」**（既定 84.0MHz）— YouTube の人気曲チャート（mostPopular / ミュージック）から選曲。
  - **「Vocaloid BOT」**（既定 90.0MHz）— 「VOCALOID / ボカロ / 初音ミク」の検索結果から選曲。
  - **曲が終わったら次曲へ**、**10分を超える長い曲は途中でスキップ**（`DJ_BOT_MAX_SECONDS`）。**埋め込み可能な通常動画のみ**を採用し、再生に失敗した曲も自動で次曲へ。Discord Webhook 設定時は「再生中」を通知。スタジオから「次の曲へ」も可能。APIキー未設定時は埋め込み可能な内蔵プールにフォールバック。
- **チューナーのスナップ移動** — 掲示板（ステーション）画面のダイヤル/スライダーは、離したときに近くの局（0.6MHz以内）へスナップし、その局へ移動できます。

### 認証・開局（今回の拡張）
- **アカウント & 認証** — メール/パスワード登録 + JWT。Discord OAuth2 は環境変数設定時のみ有効。
- **開局システム** — 空き周波数（76.0〜94.9MHz）の検索・取得、コールサイン／放送方針／AI DJキャラクター設定。開局するとロールが `listener` → `broadcaster` に昇格。
- **パーソナリティ権限** — BGM強制切り替え・放送/休止切替・ミュート・チャットモデレーション。
- **スタジオコントロールパネル** — 開局したステーションのリアルタイム操作。
- **プロフィール（マイページ）** — ナビのアカウント名から遷移。保有局の管理（ON AIR / 停波 / 廃局）・自分の過去の曲ログ・放送セッション・お気に入りを表示。

### 専用局（24時間常設・申請承認制）
- **ロール** — `listener`（一般）/ `dedicated_owner`（専用局マスター）/ `admin`（管理者）。
- **申請→審査→承認フロー** — 一般ユーザーが希望周波数・コールサイン・ジャンル・コンセプト・初期音源リストを提出 → 管理者が承認/却下。
- **承認で本登録** — 週波数を固定した専用局（`stations.is_dedicated=1`）を作成し、初期音源を `dedicated_track_library` へ移行、申請者を `dedicated_owner` に昇格。
- **24時間自律運行エンジン** — APScheduler（既定10秒間隔）で、リクエストキュー（`broadcast_queue`）を最優先 → 空ならライブラリからランダム送出。WebSocket で全リスナーへ即時同期。曲尺（最大10分にクランプ）経過で次曲へ。
- **管理ページ** `/admin` — 申請一覧・審査待ち/承認/却下の絞り込み・承認/却下（コメント付き）。管理者のみ表示。
- **申請ページ** `/dedicated` — 専用局の申請フォームと自分の申請状況。

### 番組表・アーカイブ（今回の拡張）
- **番組表（タイムテーブル）** — 日別・週間のラジオ番組表UI（EPG風）。
- **番組登録** — タイトル・開始/終了時間・デフォルトBGMを登録。
- **アーカイブ** — 過去番組のチャットログとBGMを「録音テープ風」に閲覧。
- **お気に入り周波数** — リスナーのプリセット保存。

### 周波数ライフサイクルエンジン（今回の拡張）
- **全190スロット管理** — 76.0〜94.9MHz（0.1MHz刻み）を `EMPTY / RESERVED / LIVE / OFF AIR` の状態で一元管理。
- **状態遷移** — `EMPTY → RESERVED（予約・開局準備中）→ OFF AIR（停波）→ ON AIR（LIVE）→ EMPTY（廃局・枠終了）`。
- **保有制約** — 1ユーザーにつき保有できる周波数は原則1つまで（管理者を除く）。
- **本開局** — `POST /api/stations/launch`。時間枠予約は `POST /api/frequencies/reserve`。
- **時間枠予約** — 周波数×時間帯の排他制御（重複時間帯の予約は 409 で拒否）。
- **番組の自動オンエア** — タイムテーブルの番組開始時刻に自動で ON AIR＋BGMセット、終了で停波。
- **リアルタイム同期** — 状態変化を WebSocket（ロビー `/ws`）で全クライアントへ配信。
- **停波の砂嵐同期** — OFF AIR のステーションはプレイヤーが砂嵐（NOISE）表示に切り替わる。
- **廃局（周波数返還）** — ステーションを閉局し、周波数スロットを EMPTY に戻す。

> 予約・番組などの時刻はサーバーのローカル時刻で統一しています（フロントの `datetime-local` と一致）。

### 公開オートアーカイブ（今回の拡張）
- **自動セッション記録** — 予約なしのゲリラ放送でも、ON AIR〜OFF AIR の1区切りを自動で「放送セッション」として記録。
- **ログ・選曲の自動バインド** — 放送中の全メッセージと YouTube 選曲を、セッションID＋開始からの経過秒で自動保存。
- **完全オープン・パブリックアクセス** — アーカイブAPIは認証不要。ログイン・予約なしで誰でも過去ログを閲覧できる。
- **タイムシフト同期再生** — 当時の YouTube 音源を再生しながら、経過秒に同期して当時のチャットが流れてくる「疑似リアルタイム再生」。

## 🧱 技術スタック

| 層 | 技術 |
| --- | --- |
| フロントエンド | Vue 3 (Composition API) + Vite + Vue Router 4 + Pinia |
| バックエンド | Python 3.9+ / FastAPI / Uvicorn / WebSockets |
| 認証 | JWT + bcrypt / Discord OAuth2（任意） |
| データベース | SQLAlchemy（デフォルトSQLite、`.env`でMySQL 8.xに切替） |
| 外部連携 | Discord Webhook / Google Gemini API |

## 📁 ディレクトリ構成

```
Midair_io/
├── backend/
│   ├── app/
│   │   ├── core/        # config / database / security / utils
│   │   ├── models/      # models.py（User / Station / Program / Message / Favorite / Reservation / BroadcastSession / SessionTrack / BotStation / DedicatedApplication / DedicatedTrackLibrary / BroadcastQueue）
│   │   ├── services/    # websocket_manager / ai_dj / discord_sync / sessions / trending / bot_dj / dedicated
│   │   ├── services/    # websocket_manager / ai_dj / discord_sync / sessions / trending / bot_dj / dedicated
│   │   ├── routers/     # auth / stations / frequencies / programs / archives / me / bot / dedicated / ws
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── database/schema.sql  # MySQL DDL（SQLite時は不要）
├── frontend/            # 唯一のフロントエンド・ソース（Vue SFC）
│   ├── src/
│   │   ├── components/  # RadioTuner / ChatStream / MessageInput / RadioPlayer / MidAirCard
│   │   ├── views/       # Home / Stations / Station / FrequencyMap / Timetable / Studio / Archive / Profile / Dedicated / Admin / Login
│   │   ├── stores/      # auth.js (Pinia)
│   │   ├── router/      # index.js（Vite=履歴 / スタンドアロン=ハッシュ）
│   │   ├── api.js       # API・WS の接続先を環境で切替
│   │   ├── App.vue
│   │   └── main.js
│   ├── vite.config.js
│   ├── vite.standalone.config.js   # Live Server 用ビルド設定
│   └── package.json
├── assets/              # 【生成物】npm run build:standalone が出力（コミット対象）
│   ├── app.js           # Vue同梱のスタンドアロンバンドル
│   └── app.css
├── index.html           # スタンドアロン用シェル（Live Server で開く）
└── README.md
```

## 🚀 起動方法

### ① バックエンド（FastAPI）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 任意
uvicorn app.main:app --reload --port 8000
```

起動時に SQLite DB・`admin` ユーザー・公式ステーション4局が自動作成されます。

- 管理者アカウント: `.env` の `ADMIN_EMAIL` / `ADMIN_PASSWORD` で設定（既定は `admin@example.com` / `change-me-admin`。初回起動時にシードされます）

### ② フロントエンド（Vite / 開発）

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173/
npm run build               # 本番ビルド → frontend/dist
```

> 周波数マップ（`/frequencies`）で全190スロットの状態確認・時間枠予約・開局・ON AIR/停波・廃局ができます。

### ③ スタンドアロン（Live Server で開く）

フロントエンドのソースは `frontend/src`（SFC）に一本化されています。
Live Server 用の `assets/app.js` は、そこから生成した**成果物**です。

```bash
cd frontend
npm run build:standalone    # → ../assets/app.js / ../assets/app.css を生成
```

①のバックエンドを起動した状態で、ルートの `index.html` を VS Code の「Open with Live Server」で開きます。
Vue もバンドルに同梱しているため **CDN に依存しません**（npm install 済みなら再ビルドのみ）。

- スタンドアロンでは自動的に**ハッシュルーティング**（`#/...`）になり、API・WebSocket は `<ホスト>:8000` を直接参照します。
- 画面・機能は Vite版と**完全に同一**です（同じ SFC をビルドしているため）。
- ナビは「ホーム / 周波数を探す / 周波数マップ / 番組表 / スタジオ」。アーカイブはホームで**未開局の周波数**に合わせたときに出る「アーカイブを開く」ボタンから（`#/archive`）。
- `frontend/index.html` を Live Server で誤って開いた場合は、自動でスタンドアロン版（直下の `index.html`）へリダイレクトします。

> `frontend/src` を変更したら、Live Server に反映するには `npm run build:standalone` を再実行してください。

## 🔌 外部連携の設定（`backend/.env`）

```ini
SECRET_KEY=...              # 32文字以上のランダム文字列
ADMIN_USERNAME=admin        # 初期管理者（初回起動時にシード）
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=...          # 必ず変更する
GEMINI_API_KEY=...          # AI DJ（未設定ならルールベース）
YOUTUBE_API_KEY=...         # DJ BOT の人気曲取得（任意）
DISCORD_CLIENT_ID=...       # Discord OAuth2（設定時のみ有効）
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback
FRONTEND_URL=http://localhost:5173
DISCORD_WEBHOOK_URL=...     # チャット→Discord同期 / DJ BOTの再生通知
DATABASE_URL=mysql+asyncmy://user:pass@localhost:3306/midair?charset=utf8mb4  # MySQL切替

DJ_BOT_ENABLED=true         # 自動DJ局（DJ BOT）を有効化
DJ_BOT_FREQUENCY=84.0       # 自動DJ局の周波数（使用中なら次の空きへ）
DJ_BOT_INTERVAL_SECONDS=180 # 曲の長さが不明なときのフォールバック秒数
DJ_BOT_MAX_SECONDS=600      # 1曲の最大再生秒数（超えたら途中スキップ）
DJ_BOT_REGION=JP            # 人気曲チャートの地域
DJ_BOT_TRENDING_CACHE_MINUTES=30  # 人気曲リストのキャッシュ時間
```

Discord→Midair.io方向は、Discordサーバー設定のWebhook送信先に
`https://<host>/api/discord/ingest?station_id=1` を指定します。

## ⚠️ 注意

- デモ用途の最小構成です。公開運用する際は認証・レート制限・モデレーション等を強化してください。
- YouTube は**音あり再生を既定**にしています。ブラウザの自動再生ポリシーでブロックされた場合は、「▶ 音を出して再生」ボタンか、画面の最初のクリックで再生が始まります（アプリ内リンクからの遷移はクリック操作があるため、そのまま音が出ます）。
