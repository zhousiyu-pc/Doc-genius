"""
Doc-genius — AI 需求与详设生成器 服务入口
========================================
通过 LLM 多轮对话理解用户意图，确认需求大纲后，
并行调用 Skills 工具链生成需求文档、流程图、ER 图、测试用例和 API 文档。

启动方式：
    python3 main.py

环境变量：
    SKILLS_PORT      - 服务端口（默认 8766）
    LLM_API_KEY      - LLM API Key
    LLM_MODEL        - LLM 模型名称（默认 qwen-plus）
    SKILLS_DATA_DIR  - 数据存储目录（默认 ~/.agent_skills）
"""

import os
import sys

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from core.config import HOST, PORT, DATA_DIR, LOG_DIR, LLM_API_KEY, LLM_MODEL, LLM_PROVIDER
from core.db import init_db
from core.error_handler import ErrorHandlerMiddleware
from core.rate_limiter import RateLimitMiddleware
from core.logger import setup_logging
from skills.conversation.routes import routes as chat_routes
from core.auth_routes import auth_routes
from skills.pipeline import init_pipeline_executor, shutdown_pipeline_executor


# ── 全局路由 ──────────────────────────────────────

async def api_health(request: Request) -> JSONResponse:
    """GET /api/health — 健康检查"""
    return JSONResponse({
        "status": "ok",
        "service": "doc_genius",
        "skills": [
            "conversation",
            "req_doc", "flow_diagram", "er_diagram", "test_cases", "api_doc",
        ],
        "port": PORT,
        "data_dir": DATA_DIR,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "llm_key_set": bool(LLM_API_KEY),
    })


all_routes = [
    Route("/api/health", api_health, methods=["GET"]),
    *auth_routes,
    *chat_routes,
]

# ── 静态文件托管（前端 dist）─────────────────────

_web_dist = os.path.join(_project_root, "web", "dist")
if os.path.isdir(_web_dist):
    _index_html = os.path.join(_web_dist, "index.html")

    async def _spa_fallback(request: Request):
        """SPA fallback：非 API 路径返回 index.html，由前端路由处理。"""
        from starlette.responses import FileResponse as FR
        return FR(_index_html)

    all_routes.append(
        Mount("/assets", app=StaticFiles(directory=os.path.join(_web_dist, "assets"))),
    )
    # SPA 通配路由（放在最后，兜底所有非 API 路径）
    all_routes.append(Route("/{path:path}", _spa_fallback, methods=["GET"]))


# ── CORS + 错误处理中间件 ─────────────────────────

ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
]

app = Starlette(routes=all_routes, middleware=middleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RateLimitMiddleware)


# ── 服务启动 ──────────────────────────────────────

def main():
    """服务启动入口"""
    import uvicorn

    setup_logging()
    init_db()
    init_pipeline_executor()

    print("=" * 60)
    print("  Doc-genius — AI 需求与详设生成器")
    print("=" * 60)
    print(f"  监听地址：    http://localhost:{PORT}")
    print(f"  数据目录：    {DATA_DIR}")
    print(f"  日志目录：    {LOG_DIR}")
    print(f"  LLM 提供商：  {LLM_PROVIDER}")
    print(f"  LLM 模型：   {LLM_MODEL}")
    print(f"  API Key：     {'已配置' if LLM_API_KEY else '未配置(请设置 LLM_API_KEY)'}")
    print(f"  前端:        {'已挂载' if os.path.isdir(_web_dist) else '未构建'}")
    print("-" * 60)
    print("  API 端点:")
    print("    POST /api/chat/sessions             创建对话")
    print("    GET  /api/chat/sessions             会话列表")
    print("    GET  /api/chat/sessions/{id}        会话详情")
    print("    POST /api/chat/sessions/{id}/messages  发送消息 (SSE)")
    print("    POST /api/chat/sessions/{id}/confirm   确认大纲")
    print("    DELETE /api/chat/sessions/{id}       删除会话")
    print("    GET  /api/health                    健康检查")
    print("=" * 60)

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    finally:
        shutdown_pipeline_executor()


if __name__ == "__main__":
    main()
