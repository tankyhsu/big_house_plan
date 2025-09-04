#!/usr/bin/env bash
# 一键启动 后端(8000) + 前端(5173)
# 使用: bash scripts/dev.sh

set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

# ---------- 后端 ----------
echo "==> [backend] 安装依赖（如已安装会跳过）"
python3 -m venv .venv >/dev/null 2>&1 || true
source .venv/bin/activate
python3 -m pip install -U pip >/dev/null
python3 -m pip install -r requirements.txt

if [ ! -f "config.yaml" ]; then
  cat > config.yaml <<'YAML'
# 基本配置（请按实际 DB 路径修改）
db_path: ./backend/data/portfolio.db
unit_amount: 3000
stop_gain_pct: 0.30
overweight_band: 0.20
ma_short: 20
ma_long: 60
ma_risk: 200
# tushare_token: "your-token"
YAML
  echo "已生成默认 config.yaml（db_path=./backend/data/portfolio.db）"
fi

echo "==> [backend] 启动 uvicorn on :8000"
# 后端放后台运行，退出时自动清理
uvicorn backend.api:app --reload --port 8000 &
BACK_PID=$!

cleanup() {
  echo "==> 清理进程..."
  kill $BACK_PID 2>/dev/null || true
}
trap cleanup EXIT

# ---------- 前端 ----------
echo "==> [frontend] 安装依赖（如已安装会跳过）"
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm i)
fi

if [ ! -f "frontend/.env" ]; then
  echo 'VITE_API_BASE=http://127.0.0.1:8000' > frontend/.env
  echo "已生成 frontend/.env"
fi

echo "==> [frontend] 启动 Vite on :5173"
cd frontend
npm run dev