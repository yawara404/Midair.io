#!/usr/bin/env bash
# MidAir バックエンド起動スクリプト（backend/ 内で実行、または引数で指定）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
cd "${BACKEND_DIR}"

if [ ! -d ".venv" ]; then
  echo ">> 仮想環境を作成します (.venv)"
  python3 -m venv .venv
fi

source .venv/bin/activate

echo ">> 依存パッケージを確認します"
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo ">> .env を作成します (.env.example からコピー)"
  cp .env.example .env
fi

echo ">> Midair.io API を起動します (http://127.0.0.1:8000)"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
