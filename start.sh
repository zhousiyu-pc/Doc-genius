#!/bin/bash
# ============================================================
#  Doc-genius — 一键启动脚本
#  用法：./start.sh [--port 8766] [--llm-key "sk-xxx"]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/.server.log"

# ── 加载 .env ──────────────────────────────────

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# ── 解析参数 ────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)      export SKILLS_PORT="$2"; shift 2 ;;
        --workers)   export TASK_WORKERS="$2"; shift 2 ;;
        --llm-key)   export LLM_API_KEY="$2"; shift 2 ;;
        --llm-model) export LLM_MODEL="$2"; shift 2 ;;
        --dev)       DEV_MODE=1; shift ;;
        -h|--help)
            echo "用法: ./start.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --port        服务端口 (默认: 8766)"
            echo "  --workers     并发 Worker 数 (默认: 3)"
            echo "  --llm-key     LLM API Key"
            echo "  --llm-model   LLM 模型名称 (默认: qwen-plus)"
            echo "  --dev         开发模式 (前端 dev server + 后端)"
            echo "  -h, --help    显示帮助"
            exit 0
            ;;
        *) echo "未知参数: $1 (使用 --help 查看可用选项)"; exit 1 ;;
    esac
done

PORT="${SKILLS_PORT:-8766}"

# ── 检查 LLM_API_KEY ─────────────────────────────

if [ -z "$LLM_API_KEY" ]; then
    echo "⚠️  LLM_API_KEY 未设置！"
    echo "请通过以下方式设置:"
    echo "  1. 创建 .env 文件: cp .env.example .env && vim .env"
    echo "  2. 环境变量: export LLM_API_KEY='sk-xxx'"
    echo "  3. 启动参数: ./start.sh --llm-key 'sk-xxx'"
    exit 1
fi

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

# ── 检查前端是否已构建 ──────────────────────────

if [ ! -d "$PROJECT_DIR/web/dist" ] && [ -z "$DEV_MODE" ]; then
    echo "前端尚未构建，正在构建..."
    if [ -d "$PROJECT_DIR/web/node_modules" ]; then
        cd "$PROJECT_DIR/web"
        NODE_OPTIONS="--max-old-space-size=768" npx vite build 2>&1
        cd "$PROJECT_DIR"
    else
        echo "⚠️  web/node_modules 不存在，请先运行: cd web && npm install"
        echo "跳过前端构建，仅启动 API 服务"
    fi
fi

# ── 启动后端服务 ────────────────────────────────

echo "启动 Doc-genius 服务 ..."

cd "$PROJECT_DIR"
nohup python3 "$SCRIPT_DIR/main.py" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# 等待服务就绪（最多 8 秒）
for i in $(seq 1 8); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "❌ 启动失败，查看日志:"
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
    echo "  Doc-genius — AI 需求与详设生成器"
    echo "=========================================="
    echo "  PID:      $SERVER_PID"
    echo "  端口:     $PORT"
    echo "  日志:     $LOG_FILE"
    if [ -d "$PROJECT_DIR/web/dist" ]; then
        echo "  前端:     http://localhost:$PORT"
    else
        echo "  前端:     未构建（仅 API 模式）"
    fi
    echo "  API:      http://localhost:$PORT/api/health"
    echo "  停止命令: $SCRIPT_DIR/stop.sh"
    echo "=========================================="

    if [ -n "$HEALTH" ]; then
        echo "  ✅ 健康检查: OK"
    else
        echo "  ⏳ 健康检查: 等待中（服务可能仍在初始化）"
    fi
    echo ""

    # 开发模式：同时启动前端 dev server
    if [ -n "$DEV_MODE" ]; then
        echo "📦 开发模式：启动前端 dev server (端口 3000) ..."
        cd "$PROJECT_DIR/web"
        npx vite --host 2>&1 &
        echo "  前端开发: http://localhost:3000"
    fi
else
    echo ""
    echo "❌ 启动失败，查看日志:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
