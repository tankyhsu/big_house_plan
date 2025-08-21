#!/usr/bin/env bash
# 快速启动 后端(8000) + 前端(5173)，跳过依赖安装
# 使用: bash scripts/dev-fast.sh

set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

# ---------- 后端 ----------
echo "==> [backend] 启动 uvicorn on :8000"
source .venv/bin/activate
uvicorn backend.api:app --reload --port 8000 &
BACK_PID=$!

cleanup() {
  echo "==> 清理进程..."
  kill $BACK_PID 2>/dev/null || true
}
trap cleanup EXIT

# ---------- 前端 ----------
echo "==> [frontend] 启动 Vite on :5173"
cd frontend
npm run dev