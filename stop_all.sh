#!/bin/bash
# ============================================================
#  Doc-genius — 一键停止（前端 + 后端）
#  用法：./stop_all.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_PID_FILE="$SCRIPT_DIR/.web.pid"
WEB_PORT=3000

# ── 1) 停止前端 ───────────────────────────────────

echo "停止前端服务 ..."
if [ -f "$WEB_PID_FILE" ]; then
  WEB_PID=$(cat "$WEB_PID_FILE" 2>/dev/null || true)
  if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
    echo "正在停止前端 (PID: $WEB_PID) ..."
    kill "$WEB_PID" 2>/dev/null || true
    for i in $(seq 1 10); do
      if ! kill -0 "$WEB_PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$WEB_PID" 2>/dev/null; then
      echo "优雅停止超时，强制终止前端 ..."
      kill -9 "$WEB_PID" 2>/dev/null || true
    fi
  fi
  rm -f "$WEB_PID_FILE"
else
  echo "未找到前端 PID 文件"
fi

# 清理前端端口残留
EXISTING=$(lsof -ti:"$WEB_PORT" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "清理前端端口 $WEB_PORT 上的残留进程: $EXISTING"
  echo "$EXISTING" | xargs kill 2>/dev/null || true
  sleep 1
fi

# ── 2) 停止后端 ───────────────────────────────────

echo ""
echo "停止后端服务 ..."
"$SCRIPT_DIR/stop.sh" || true

echo ""
echo "=========================================="
echo "  ✅ Doc-genius 前后端已停止"
echo "=========================================="
echo ""

