#!/usr/bin/env bash
#
# MidAir ローカル開発 起動スクリプト
#
# 以下を起動します:
#   1) バックエンド   (FastAPI / Uvicorn --reload) : http://127.0.0.1:8000
#   2) フロントエンド (Vite dev server)            : http://localhost:5173/
#
# Vite の dev server は /api と /ws を http://localhost:8000 へプロキシします。
#
# 使い方:
#   ./local_start.sh            # 起動（backend + Vite dev）
#   ./local_start.sh backend    # バックエンドのみ起動（フロントは起動しない）
#   ./local_start.sh stop       # 停止
#   ./local_start.sh restart    # 再起動
#   ./local_start.sh status     # 状態表示
#
# ログ: logs/local_backend.log / logs/local_frontend.log
# 停止: フォアグラウンドで Ctrl+C
#
# 注意: 公開用 ./start.sh と同じポート 8000 を使うため、同時には起動できません。
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"
LOG_DIR="${SCRIPT_DIR}/logs"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="5173"

# 既存プロセス検出・停止用のパターン（他サービスを巻き込まないよう具体的に指定）
PATTERNS=(
  "uvicorn app.main:app"
  "${FRONTEND_DIR}/node_modules"
)

BACKEND_PID=""
FRONTEND_PID=""

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
  local quiet="${1:-}" pattern pids killed=0
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
    printf '  [%s] %-44s %s\n' "$label" "$pattern" "$pids"
  done
  printf '\n  フロント : http://localhost:%s/\n' "$FRONTEND_PORT"
  printf '  API      : http://%s:%s/docs\n' "$BACKEND_HOST" "$BACKEND_PORT"
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
}

setup_frontend() {
  if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    need_cmd npm
    log "フロントの依存パッケージをインストールします (npm install)"
    ( cd "$FRONTEND_DIR" && npm install )
  fi
}

start_backend() {
  log "バックエンドを起動します (http://${BACKEND_HOST}:${BACKEND_PORT}, --reload)"
  (
    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/uvicorn" app.main:app \
      --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload \
      >> "${LOG_DIR}/local_backend.log" 2>&1 &
    echo $! > "${LOG_DIR}/local_backend.pid"
  )
}

start_frontend() {
  log "フロント(Vite dev)を起動します (http://localhost:${FRONTEND_PORT})"
  (
    cd "$FRONTEND_DIR"
    nohup ./node_modules/.bin/vite \
      >> "${LOG_DIR}/local_frontend.log" 2>&1 &
    echo $! > "${LOG_DIR}/local_frontend.pid"
  )
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
  warn "バックエンドが応答しません。${LOG_DIR}/local_backend.log を確認してください。"
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
  local with_frontend="${1:-yes}"

  need_cmd python3
  need_cmd curl

  mkdir -p "$LOG_DIR"

  # 再実行時にポート衝突しないよう、既存の開発プロセスを停止
  stop_all quiet
  wait_port_free "$BACKEND_PORT" || die "ポート ${BACKEND_PORT} が使用中です（./start.sh が起動中ではありませんか？）。"
  if [ "$with_frontend" = "yes" ]; then
    wait_port_free "$FRONTEND_PORT" || warn "ポート ${FRONTEND_PORT} が使用中です。Vite は別ポートで起動します。"
  fi

  setup_venv
  ensure_env

  trap cleanup INT TERM

  start_backend
  if [ "$with_frontend" = "yes" ]; then
    setup_frontend
    start_frontend
  fi

  if ! wait_backend_ready; then
    cleanup
    exit 1
  fi

  printf '\n============================================================\n'
  printf '  MidAir.io ローカル開発サーバー 起動完了\n'
  printf '============================================================\n'
  if [ "$with_frontend" = "yes" ]; then
    printf '  フロント : http://localhost:%s/\n' "$FRONTEND_PORT"
  fi
  printf '  API      : http://%s:%s/docs\n' "$BACKEND_HOST" "$BACKEND_PORT"
  printf '  health   : http://%s:%s/health\n\n' "$BACKEND_HOST" "$BACKEND_PORT"
  printf '  ログ:\n'
  printf '    tail -f %s/local_backend.log\n' "$LOG_DIR"
  if [ "$with_frontend" = "yes" ]; then
    printf '    tail -f %s/local_frontend.log\n' "$LOG_DIR"
  fi
  printf '\n  停止: Ctrl+C （または別ターミナルで ./local_start.sh stop）\n'
  printf '============================================================\n\n'

  log "起動中... (Ctrl+C で停止)"
  wait
}

case "${1:-start}" in
  start)
    start_all yes
    ;;
  backend)
    start_all no
    ;;
  stop)
    stop_all
    log "停止しました"
    ;;
  restart)
    stop_all quiet
    start_all yes
    ;;
  status)
    printf 'MidAir.io ローカル開発 稼働状況:\n\n'
    status_all
    ;;
  *)
    die "使い方: $0 {start|backend|stop|restart|status}"
    ;;
esac
