"""
Agent Skills Server — 统一入口
================================
整合文件保存和任务管理两个 Skill 的单一服务。
同时提供 REST API 和 MCP SSE 协议接入。

启动方式：
    python3 -m agent_skills_server.main

    或直接：
    python3 agent_skills_server/main.py

环境变量：
    SKILLS_PORT      - 服务端口（默认 8766）
    LLM_API_KEY      - LLM API Key（默认已内置）
    LLM_MODEL        - LLM 模型名称（默认 qwen-plus）
    TASK_WORKERS     - 并发 Worker 数量（默认 3）
    SKILLS_DATA_DIR  - 数据存储目录（默认 ~/.agent_skills）
    DEFAULT_SAVE_DIR - 默认文件保存目录
"""

import os
import sys

# 确保项目根目录在 sys.path 中，支持 python3 agent_skills_server/main.py 直接运行
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent_skills_server.core.config import (
    HOST, PORT, DATA_DIR, LOG_DIR,
    LLM_API_KEY, LLM_MODEL, TASK_WORKERS, DEFAULT_SAVE_DIR,
)
from agent_skills_server.core.db import init_db
from agent_skills_server.core.logger import setup_logging
from agent_skills_server.skills.file_saver.routes import routes as file_routes
from agent_skills_server.skills.task_manager.routes import routes as task_routes
from agent_skills_server.skills.task_manager.service import (
    init_executor, shutdown_executor, recover_tasks,
)


# ── 全局路由 ──────────────────────────────────────

async def api_health(request: Request) -> JSONResponse:
    """GET /api/health — 统一健康检查"""
    return JSONResponse({
        "status": "ok",
        "service": "agent_skills_server",
        "skills": ["file_saver", "task_manager"],
        "port": PORT,
        "workers": TASK_WORKERS,
        "data_dir": DATA_DIR,
        "llm_model": LLM_MODEL,
        "llm_key_set": bool(LLM_API_KEY),
        "default_save_dir": DEFAULT_SAVE_DIR,
    })


all_routes = [
    Route("/api/health", api_health, methods=["GET"]),
    *file_routes,
    *task_routes,
]

app = Starlette(routes=all_routes)


def main():
    """服务启动入口"""
    import uvicorn

    setup_logging()
    init_db()
    init_executor()
    recover_tasks()

    print("=" * 60)
    print("  Agent Skills Server")
    print("=" * 60)
    print(f"  监听地址：    http://localhost:{PORT}")
    print(f"  数据目录：    {DATA_DIR}")
    print(f"  日志目录：    {LOG_DIR}")
    print(f"  并发 Worker： {TASK_WORKERS}")
    print(f"  LLM 模型：   {LLM_MODEL}")
    print(f"  API Key：     {'已配置' if LLM_API_KEY else '未配置(请设置 LLM_API_KEY)'}")
    print(f"  默认保存目录：{DEFAULT_SAVE_DIR}")
    print("-" * 60)
    print("  Skills:")
    print("    [文件保存]  POST /api/files/save")
    print("               GET  /api/files/directories")
    print("    [任务管理]  POST /api/tasks")
    print("               GET  /api/tasks/{id}")
    print("               GET  /api/tasks/{id}/results")
    print("               POST /api/tasks/{id}/retry")
    print("    [健康检查]  GET  /api/health")
    print("=" * 60)

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    finally:
        shutdown_executor()


if __name__ == "__main__":
    main()
