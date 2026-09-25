#!/usr/bin/env bash
#
# MidAir Web公開サーバー 起動スクリプト
#
# 以下を一括起動します:
#   1) バックエンド   (FastAPI / Uvicorn)   : http://127.0.0.1:8000
#   2) フロント静的配信 (serve_frontend.py) : http://127.0.0.1:8090/Midair.io/
#   3) Cloudflare Tunnel (midair)          : 公開URLへの入口
#
# 公開URL: https://music.wawa-app.me/Midair.io/
#
# 使い方:
#   ./start.sh            # 起動（既存の MidAir プロセスは停止してから起動）
#   ./start.sh start      # 同上
#   ./start.sh stop       # 停止
#   ./start.sh restart    # 再起動
#   ./start.sh status     # 状態表示
#
# ログ: logs/backend.log / logs/frontend.log / logs/tunnel.log
# 停止: フォアグラウンドで Ctrl+C（起動したプロセスをまとめて終了）
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
LOG_DIR="${SCRIPT_DIR}/logs"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="8090"
ROOT_PATH="/Midair.io"
TUNNEL_NAME="midair"

# 既存プロセス検出・停止用のパターン（他サービスを巻き込まないよう具体的に指定）
PATTERNS=(
  "uvicorn app.main:app"
  "serve_frontend.py"
  "cloudflared tunnel run ${TUNNEL_NAME}"
)

BACKEND_PID=""
FRONTEND_PID=""
TUNNEL_PID=""

log() { printf '>> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }
die() { printf '!! %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 が見つかりません。インストールしてから再実行してください。"
}

find_pids() {
  local pattern="$1"
  pgrep -f "$pattern" 2>/dev/null || true
}

stop_all() {
  local quiet="${1:-}" pattern pids pid killed=0
  for pattern in "${PATTERNS[@]}"; do
    pids="$(find_pids "$pattern")"
    if [ -z "$pids" ]; then
      continue
    fi
    if [ -z "$quiet" ]; then
      log "停止: ${pattern} (PID: $(echo "$pids" | tr '\n' ' '))"
    fi
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    killed=1
  done

  if [ "$killed" -eq 0 ]; then
    return 0
  fi

  # 終了を待ち、残っていれば強制終了
  local i
  for i in $(seq 1 20); do
    local remaining=""
    for pattern in "${PATTERNS[@]}"; do
      remaining="${remaining}$(find_pids "$pattern")"
    done
    if [ -z "$remaining" ]; then
      return 0
    fi
    sleep 0.5
  done
  for pattern in "${PATTERNS[@]}"; do
    pkill -9 -f "$pattern" 2>/dev/null || true
  done
  return 0
}

status_all() {
  local pattern pids label
  for pattern in "${PATTERNS[@]}"; do
    pids="$(find_pids "$pattern" | tr '\n' ' ')"
    if [ -n "${pids// /}" ]; then
      label="起動中"
    else
      label="停止中"
      pids=""
    fi
    printf '  [%s] %-32s %s\n' "$label" "$pattern" "$pids"
  done
  printf '\n  公開URL: https://music.wawa-app.me%s/\n' "$ROOT_PATH"
}

wait_port_free() {
  local port="$1" i
  for i in $(seq 1 30); do
    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

setup_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    log "仮想環境を作成します (backend/.venv)"
    python3 -m venv "$VENV_DIR"
  fi
  log "依存パッケージを確認します"
  "$VENV_DIR/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
}

ensure_env() {
  local env_file="${BACKEND_DIR}/.env"
  if [ ! -f "$env_file" ]; then
    log ".env を作成します (.env.example からコピー)"
    cp "${BACKEND_DIR}/.env.example" "$env_file"
  fi

  # 公開（サブパス /Midair.io）には ROOT_PATH が必須。
  # .env.example には含まれないため、無ければ追記し、空なら値を入れる。
  if ! grep -q '^ROOT_PATH=' "$env_file"; then
    log ".env に ROOT_PATH=${ROOT_PATH} を追記します"
    {
      printf '\n# --- サブパス配信（Cloudflare Tunnel 経由 %s/） ---\n' "$ROOT_PATH"
      printf 'ROOT_PATH=%s\n' "$ROOT_PATH"
    } >> "$env_file"
  elif grep -q '^ROOT_PATH=[[:space:]]*$' "$env_file"; then
    log ".env の空の ROOT_PATH を ${ROOT_PATH} に設定します"
    local tmp
    tmp="$(mktemp)"
    sed "s|^ROOT_PATH=.*|ROOT_PATH=${ROOT_PATH}|" "$env_file" > "$tmp" && mv "$tmp" "$env_file"
  fi
}

build_frontend_if_needed() {
  if [ -f "${SCRIPT_DIR}/frontend/dist/index.html" ]; then
    return 0
  fi
  need_cmd npm
  log "フロント静的ファイルが無いためビルドします (BASE_PATH=${ROOT_PATH}/)"
  ( cd "${SCRIPT_DIR}/frontend" && npm install && BASE_PATH="${ROOT_PATH}/" npm run build )
}

start_backend() {
  log "バックエンドを起動します (http://${BACKEND_HOST}:${BACKEND_PORT})"
  (
    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/uvicorn" app.main:app \
      --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
      >> "${LOG_DIR}/backend.log" 2>&1 &
    echo $! > "${LOG_DIR}/backend.pid"
  )
}

start_frontend() {
  log "フロント静的配信を起動します (http://${BACKEND_HOST}:${FRONTEND_PORT}${ROOT_PATH}/)"
  PORT="$FRONTEND_PORT" nohup python3 "${SCRIPT_DIR}/serve_frontend.py" \
    >> "${LOG_DIR}/frontend.log" 2>&1 &
  echo $! > "${LOG_DIR}/frontend.pid"
}

start_tunnel() {
  log "Cloudflare Tunnel を起動します (tunnel: ${TUNNEL_NAME})"
  nohup cloudflared tunnel run "$TUNNEL_NAME" \
    >> "${LOG_DIR}/tunnel.log" 2>&1 &
  echo $! > "${LOG_DIR}/tunnel.pid"
}

wait_backend_ready() {
  log "バックエンドの応答を待機中..."
  local i
  for i in $(seq 1 40); do
    if curl -fsS -m 2 "http://${BACKEND_HOST}:${BACKEND_PORT}/health" >/dev/null 2>&1; then
      log "バックエンド準備完了"
      return 0
    fi
    sleep 1
  done
  warn "バックエンドが応答しません。${LOG_DIR}/backend.log を確認してください。"
  return 1
}

cleanup() {
  trap - INT TERM
  echo
  log "停止します..."
  stop_all quiet
  log "停止しました"
}

start_all() {
  need_cmd cloudflared
  need_cmd python3
  need_cmd curl

  mkdir -p "$LOG_DIR"

  # 再実行時にポート衝突しないよう、既存の MidAir プロセスを停止
  stop_all quiet
  wait_port_free "$BACKEND_PORT" || die "ポート ${BACKEND_PORT} が使用中です。"
  wait_port_free "$FRONTEND_PORT" || die "ポート ${FRONTEND_PORT} が使用中です。"

  setup_venv
  ensure_env
  build_frontend_if_needed

  trap cleanup INT TERM

  start_backend
  start_frontend
  start_tunnel

  if ! wait_backend_ready; then
    cleanup
    exit 1
  fi

  cat <<EOF

============================================================
  MidAir.io Web公開サーバー 起動完了
============================================================
  公開URL : https://music.wawa-app.me${ROOT_PATH}/
  ローカル : http://${BACKEND_HOST}:${FRONTEND_PORT}${ROOT_PATH}/
  API     : http://${BACKEND_HOST}:${BACKEND_PORT}/docs

  ログ:
    tail -f ${LOG_DIR}/backend.log
    tail -f ${LOG_DIR}/frontend.log
    tail -f ${LOG_DIR}/tunnel.log

  停止: Ctrl+C （または別ターミナルで ./start.sh stop）
============================================================
EOF

  log "起動中... (Ctrl+C で停止)"
  wait
}

case "${1:-start}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    log "停止しました"
    ;;
  restart)
    stop_all quiet
    start_all
    ;;
  status)
    printf 'MidAir.io 稼働状況:\n\n'
    status_all
    ;;
  *)
    die "使い方: $0 {start|stop|restart|status}"
    ;;
esac
