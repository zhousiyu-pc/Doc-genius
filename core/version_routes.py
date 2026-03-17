"""
版本管理 REST API
=================
会话版本的保存、列表与恢复。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.versions import save_version, list_versions, restore_version

logger = logging.getLogger("agent_skills.version_routes")


async def api_save_version(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/versions — 保存版本快照"""
    session_id = request.path_params["id"]
    title = ""
    try:
        body = await request.json()
        title = body.get("title", "")
    except Exception:
        pass  # body 可选

    try:
        version = save_version(session_id, title)
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=404)

    return JSONResponse({"success": True, "version": version})


async def api_list_versions(request: Request) -> JSONResponse:
    """GET /api/chat/sessions/{id}/versions — 列出版本列表"""
    session_id = request.path_params["id"]
    versions = list_versions(session_id)
    return JSONResponse({"success": True, "versions": versions})


async def api_restore_version(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/versions/{vid}/restore — 恢复到指定版本"""
    session_id = request.path_params["id"]
    version_id = request.path_params["vid"]
    ok = restore_version(session_id, version_id)
    if not ok:
        return JSONResponse(
            {"success": False, "message": "版本不存在或不属于该会话"},
            status_code=404,
        )
    return JSONResponse({"success": True, "message": "版本恢复成功"})


version_routes = [
    Route("/api/chat/sessions/{id}/versions", api_save_version, methods=["POST"]),
    Route("/api/chat/sessions/{id}/versions", api_list_versions, methods=["GET"]),
    Route("/api/chat/sessions/{id}/versions/{vid}/restore", api_restore_version, methods=["POST"]),
]
