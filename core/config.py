"""
全局配置模块
==========
统一管理所有环境变量和配置项。
支持通过环境变量覆盖默认值。
"""

import os
from pathlib import Path


# ── 服务配置 ──────────────────────────────────────

HOST = "0.0.0.0"
PORT = int(os.environ.get("SKILLS_PORT", "8766"))

# ── LLM 配置（通义千问 Qwen） ──────────────────────

LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-c158df64ece64143b8ee42975ed5d565")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")

# ── 任务管理配置 ──────────────────────────────────

TASK_WORKERS = int(os.environ.get("TASK_WORKERS", "1"))
MAX_RETRIES = 3
RETRY_INTERVALS = [15, 30, 60]

# ── 数据存储配置 ──────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.expanduser(os.environ.get("SKILLS_DATA_DIR", "~/.agent_skills"))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
DB_PATH = os.path.join(DATA_DIR, "tasks.db")

# ── 文件保存配置 ──────────────────────────────────

DEFAULT_SAVE_DIR = os.path.expanduser(
    os.environ.get("DEFAULT_SAVE_DIR", "~/Documents/ERP需求文档")
)

# ── 初始化目录 ────────────────────────────────────

Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
