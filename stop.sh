#!/bin/bash
# ============================================================
#  Doc-genius — 停止脚本
#  用法：./stop.sh
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
PORT="${SKILLS_PORT:-8766}"

# ── 停止主进程 ──────────────────────────────────

stop_by_pid() {
    local PID=$1
    echo "正在停止 Doc-genius 服务 (PID: $PID) ..."
    kill "$PID" 2>/dev/null

    for i in $(seq 1 10); do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "进程已正常退出"
            return 0
        fi
        sleep 1
    done

    echo "优雅停止超时，强制终止 ..."
    kill -9 "$PID" 2>/dev/null
    sleep 1
    return 0
}

# ── 清理端口残留进程 ────────────────────────────

cleanup_port() {
    PIDS=$(lsof -ti:"$PORT" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "清理端口 $PORT 上的残留进程: $PIDS"
        echo "$PIDS" | xargs kill 2>/dev/null
        sleep 1
    fi
}

# ── 主逻辑 ──────────────────────────────────────

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        stop_by_pid "$PID"
    else
        echo "PID 文件记录的进程 ($PID) 已不存在"
    fi
    rm -f "$PID_FILE"
else
    echo "未找到 PID 文件"
fi

cleanup_port

echo ""
echo "=========================================="
echo "  Doc-genius 服务已停止"
echo "=========================================="
echo ""
