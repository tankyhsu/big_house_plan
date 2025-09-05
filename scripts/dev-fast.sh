#!/usr/bin/env bash
# 快速启动 后端(8000) + 前端(5173)，跳过依赖安装
# 使用: bash scripts/dev-fast.sh

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
echo "==> [backend] 启动 uvicorn on :8000"
# 激活虚拟环境（如果存在）
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi
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
echo "==> [frontend] 启动 Vite on :5173"
cd frontend
# 强制使用固定端口，如果占用则报错退出
npm run dev -- --port 5173 --strictPort