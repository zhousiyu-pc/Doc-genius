#!/bin/bash
# 快速安装脚本
# 用于一键安装项目依赖并启动服务

set -e

echo "=========================================="
echo "  智能文档生成器 - 快速安装"
echo "=========================================="

# 检查 Python 版本
echo "📌 检查 Python 版本..."
python3 --version

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
pip3 install -r requirements.txt

# 检查是否有前端依赖
if [ -d "web" ]; then
    echo "📦 安装前端依赖..."
    cd web
    npm install
    cd ..
fi

# 提示设置 API Key
echo ""
echo "=========================================="
echo "  ⚠️  请设置 LLM API Key"
echo "=========================================="
echo ""
echo "方式 1: 环境变量"
echo "  export LLM_API_KEY=\"sk-你的 APIKey\""
echo ""
echo "方式 2: 创建 .env 文件"
echo "  echo 'LLM_API_KEY=sk-你的 APIKey' > .env"
echo ""

# 询问是否启动服务
read -p "是否现在启动服务？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 启动服务..."
    ./start.sh
fi

echo ""
echo "=========================================="
echo "  ✅ 安装完成！"
echo "=========================================="
echo ""
echo "访问地址："
echo "  API:  http://localhost:8766"
echo "  Web:  http://localhost:3000 (需运行 npm run dev)"
echo ""
