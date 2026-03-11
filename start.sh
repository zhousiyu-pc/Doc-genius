#!/bin/bash
# ============================================================
#  Agent Skills Server — 启动脚本
#  用法：./start.sh [--port 8766] [--workers 3]
#        ./start.sh --llm-key "sk-xxxxx" --llm-model "qwen-plus"
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/.server.log"

# ── 解析参数 ────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)     export SKILLS_PORT="$2"; shift 2 ;;
        --workers)  export TASK_WORKERS="$2"; shift 2 ;;
        --llm-key)   export LLM_API_KEY="$2"; shift 2 ;;
        --llm-model) export LLM_MODEL="$2"; shift 2 ;;
        -h|--help)
            echo "用法: ./start.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --port        服务端口 (默认: 8766)"
            echo "  --workers     并发 Worker 数 (默认: 3)"
            echo "  --llm-key     LLM API Key (默认已内置)"
            echo "  --llm-model   LLM 模型名称 (默认: qwen-plus)"
            echo "  -h, --help    显示帮助"
            exit 0
            ;;
        *) echo "未知参数: $1 (使用 --help 查看可用选项)"; exit 1 ;;
    esac
done

PORT="${SKILLS_PORT:-8766}"

# ── 检查是否已在运行 ────────────────────────────

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "服务已在运行 (PID: $OLD_PID, 端口: $PORT)"
        echo "如需重启，请先执行 ./stop.sh"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# ── 检查端口占用 ────────────────────────────────

EXISTING=$(lsof -ti:"$PORT" 2>/dev/null)
if [ -n "$EXISTING" ]; then
    echo "警告: 端口 $PORT 已被占用 (PID: $EXISTING)"
    echo "正在释放端口 ..."
    echo "$EXISTING" | xargs kill 2>/dev/null
    sleep 1
fi

# ── 激活 conda 环境 ─────────────────────────────

if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook 2>/dev/null)"
    conda activate tf_metal 2>/dev/null
fi

# ── 启动服务 ────────────────────────────────────

echo "启动 Agent Skills Server ..."

cd "$PROJECT_DIR"
nohup python3 "$SCRIPT_DIR/main.py" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# 等待服务就绪（最多 8 秒）
for i in $(seq 1 8); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "启动失败，查看日志:"
        tail -20 "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
    HEALTH=$(curl -s --max-time 2 "http://localhost:$PORT/api/health" 2>/dev/null)
    if [ -n "$HEALTH" ]; then
        break
    fi
    sleep 1
done

if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo ""
    echo "=========================================="
    echo "  Agent Skills Server 已启动"
    echo "=========================================="
    echo "  PID:      $SERVER_PID"
    echo "  端口:     $PORT"
    echo "  日志:     $LOG_FILE"
    echo "  停止命令: $SCRIPT_DIR/stop.sh"
    echo "=========================================="

    if [ -n "$HEALTH" ]; then
        echo "  健康检查: OK"
    else
        echo "  健康检查: 等待中（服务可能仍在初始化）"
    fi
    echo ""
else
    echo ""
    echo "启动失败，查看日志:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
