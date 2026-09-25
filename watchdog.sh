#!/bin/bash
# Midair.io バックエンド監視（ハング・停止時に自動で再起動する）
#
# 使い方:
#   ./watchdog.sh            # フォアグラウンドで監視
#   nohup ./watchdog.sh &    # バックグラウンドで監視
#
# /health が連続で失敗したら uvicorn を強制再起動します。

cd "$(dirname "$0")" || exit 1
BACKEND_DIR="$(pwd)/backend"
LOG="${MIDAIR_UVICORN_LOG:-/private/var/folders/vf/pwt_8g7j3zd5q4b_xnrmjfhr0000gq/T/opencode/midair_uvicorn.log}"
HEALTH_URL="http://127.0.0.1:8000/health"
INTERVAL=30
MAX_FAILS=2

fails=0
while true; do
  code=$(curl -s -o /dev/null -m 6 -w "%{http_code}" "$HEALTH_URL")
  if [ "$code" = "200" ]; then
    fails=0
  else
    fails=$((fails + 1))
    echo "$(date '+%F %T') [watchdog] health=$code fails=$fails"
    if [ "$fails" -ge "$MAX_FAILS" ]; then
      echo "$(date '+%F %T') [watchdog] uvicorn を再起動します"
      pkill -9 -f "uvicorn app.main:app" 2>/dev/null
      sleep 2
      cd "$BACKEND_DIR" || exit 1
      nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "$LOG" 2>&1 &
      fails=0
      sleep 15
    fi
  fi
  sleep "$INTERVAL"
done
