"""
文件保存 Skill — REST API 路由
"""

import os
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ...core.config import DEFAULT_SAVE_DIR
from .service import save_file

logger = logging.getLogger("agent_skills.file_saver")


async def api_save(request: Request) -> JSONResponse:
    """
    POST /api/files/save — 保存 Markdown 文件

    请求体 JSON：
      {
        "content": "Markdown 内容",
        "filename": "可选文件名",
        "save_directory": "可选保存目录"
      }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "message": "请求体必须为有效的 JSON"},
            status_code=400,
        )

    result = save_file(
        content=body.get("content", ""),
        filename=body.get("filename", ""),
        save_directory=body.get("save_directory", ""),
    )
    status_code = 200 if result["success"] else 400
    return JSONResponse(result, status_code=status_code)


async def api_directories(request: Request) -> JSONResponse:
    """GET /api/files/directories — 列出常用保存目录"""
    home = os.path.expanduser("~")
    candidates = [
        {"path": DEFAULT_SAVE_DIR, "label": "默认目录"},
        {"path": os.path.join(home, "Documents"), "label": "文档"},
        {"path": os.path.join(home, "Desktop"), "label": "桌面"},
        {"path": os.path.join(home, "Downloads"), "label": "下载"},
    ]
    for c in candidates:
        c["exists"] = os.path.isdir(c["path"])
    return JSONResponse({"directories": candidates})


routes = [
    Route("/api/files/save", api_save, methods=["POST"]),
    Route("/api/files/directories", api_directories, methods=["GET"]),
]
