#!/bin/bash
# ============================================================
#  Doc-genius — 一键启动（前端 + 后端）
#  用法：
#    ./start_all.sh
#    ./start_all.sh --port 8766 --workers 3
#    ./start_all.sh --web-port 3000
#    ./start_all.sh --llm-key "sk-xxx" --llm-model "qwen-plus"
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$SCRIPT_DIR/web"
WEB_PID_FILE="$SCRIPT_DIR/.web.pid"
WEB_LOG_FILE="$SCRIPT_DIR/.web.log"

WEB_PORT=3000

# ── 解析参数（后端参数透传给 ./start.sh）────────────────────────

BACKEND_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-port) WEB_PORT="$2"; shift 2 ;;
    *) BACKEND_ARGS+=("$1"); shift ;;
  esac
done

# ── 激活 conda 环境（如存在）───────────────────────────────────

if command -v conda &>/dev/null; then
  eval "$(conda shell.bash hook 2>/dev/null)"
  conda activate tf_metal 2>/dev/null || true
fi

echo "=========================================="
echo "  Doc-genius 一键启动"
echo "=========================================="

# ── 1) 启动后端（沿用现有脚本）─────────────────────────────────

echo ""
echo "[1/2] 启动后端服务 ..."
"$SCRIPT_DIR/start.sh" "${BACKEND_ARGS[@]}"

# ── 2) 启动前端（Vite Dev Server）──────────────────────────────

echo ""
echo "[2/2] 启动前端服务 ..."

if [ ! -d "$WEB_DIR" ]; then
  echo "未找到前端目录：$WEB_DIR"
  exit 1
fi

if [ -f "$WEB_PID_FILE" ]; then
  OLD_WEB_PID=$(cat "$WEB_PID_FILE" 2>/dev/null || true)
  if [ -n "$OLD_WEB_PID" ] && kill -0 "$OLD_WEB_PID" 2>/dev/null; then
    echo "前端已在运行 (PID: $OLD_WEB_PID, 端口: $WEB_PORT)"
  else
    rm -f "$WEB_PID_FILE"
  fi
fi

# 若端口已被占用，尝试释放
EXISTING=$(lsof -ti:"$WEB_PORT" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "警告: 前端端口 $WEB_PORT 已被占用 (PID: $EXISTING)"
  echo "正在释放端口 ..."
  echo "$EXISTING" | xargs kill 2>/dev/null || true
  sleep 1
fi

cd "$WEB_DIR"

# ── Node 版本检查（Vite 5 需要 Node >= 18），自动尝试切换 ────────

# 先尝试加载 nvm，使脚本能自动切换 Node 版本
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh" 2>/dev/null || true
[ -s "/usr/local/opt/nvm/nvm.sh" ] && source "/usr/local/opt/nvm/nvm.sh" 2>/dev/null || true

if ! command -v node &>/dev/null; then
  echo "未检测到 node，请先安装 Node.js（建议 18 或 20）"
  exit 1
fi

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo "0")
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "当前 Node.js $(node -v) 版本过低，自动切换到 Node 18 ..."
  if command -v nvm &>/dev/null; then
    nvm use 18 2>/dev/null || nvm use 20 2>/dev/null || {
      echo "nvm 切换失败，请手动执行: nvm use 18"
      exit 1
    }
    NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo "0")
    echo "已切换到 Node.js $(node -v)"
  else
    echo "未找到 nvm，无法自动切换。请手动安装 Node 18+："
    echo "  https://nodejs.org/"
    exit 1
  fi
fi

# node_modules 不存在，或之前是低版本 Node 装的（可能缺少 native 包），自动重装
NEED_REINSTALL=false
if [ ! -d "node_modules" ]; then
  NEED_REINSTALL=true
  echo "检测到 node_modules 不存在，执行 npm install ..."
elif [ ! -d "node_modules/@rollup/rollup-darwin-x64" ] && [ "$(uname -m)" = "x86_64" ]; then
  NEED_REINSTALL=true
  echo "检测到 rollup native 包缺失（可能是 Node 版本切换导致），重新安装依赖 ..."
elif [ ! -d "node_modules/@rollup/rollup-darwin-arm64" ] && [ "$(uname -m)" = "arm64" ]; then
  NEED_REINSTALL=true
  echo "检测到 rollup native 包缺失（可能是 Node 版本切换导致），重新安装依赖 ..."
fi

if [ "$NEED_REINSTALL" = true ]; then
  rm -rf node_modules package-lock.json 2>/dev/null || true
  npm install --registry=https://registry.npmmirror.com
fi

nohup npm run dev -- --port "$WEB_PORT" > "$WEB_LOG_FILE" 2>&1 &
WEB_PID=$!
echo "$WEB_PID" > "$WEB_PID_FILE"

# 等待前端就绪（最多 10 秒）
for i in $(seq 1 10); do
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo ""
    echo "前端启动失败，查看日志:"
    tail -30 "$WEB_LOG_FILE" || true
    rm -f "$WEB_PID_FILE"
    exit 1
  fi
  WEB_OK=$(curl -s --max-time 2 "http://localhost:$WEB_PORT" 2>/dev/null || true)
  if [ -n "$WEB_OK" ]; then
    break
  fi
  sleep 1
done

echo ""
echo "=========================================="
echo "  ✅ 启动完成"
echo "=========================================="
echo "  后端 API:  http://localhost:${SKILLS_PORT:-8766}"
echo "  前端 Web:  http://localhost:${WEB_PORT}"
echo "  前端 PID:  $WEB_PID"
echo "  前端日志:  $WEB_LOG_FILE"
echo "  停止命令:  $SCRIPT_DIR/stop_all.sh"
echo "=========================================="
echo ""

