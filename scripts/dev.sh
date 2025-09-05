#!/usr/bin/env bash
# 一键启动 后端(8000) + 前端(5173)
# 使用: bash scripts/dev.sh

set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

# 清理端口占用的函数
kill_port() {
  local port=$1
  echo "==> 检查端口 :$port 占用情况"
  local pids=$(lsof -t -i :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "==> 发现端口 :$port 被占用，正在清理进程: $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 1
  else
    echo "==> 端口 :$port 未被占用"
  fi
}

# 清理后端和前端端口
kill_port 8000
kill_port 5173

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
uvicorn backend.api:app --reload --port 8000 --host 0.0.0.0 &
BACK_PID=$!

cleanup() {
  echo "==> 清理进程..."
  kill $BACK_PID 2>/dev/null || true
  # 确保端口完全释放
  kill_port 8000
  kill_port 5173
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
# 强制使用固定端口，如果占用则报错退出
npm run dev -- --port 5173 --strictPort