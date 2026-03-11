# Agent Skills Server - Dockerfile
# =================================
# 多阶段构建，优化镜像大小

# ── 构建阶段 ──────────────────────────────────────
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# ── 运行阶段 ──────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser

# 从构建阶段复制依赖
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY --chown=appuser:appuser . .

# 设置环境变量
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SKILLS_PORT=8766 \
    SKILLS_DATA_DIR=/app/data \
    LOG_DIR=/app/logs

# 创建数据目录
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app/data /app/logs

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8766

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/api/health')" || exit 1

# 启动命令
CMD ["python", "main.py"]
