"""
分享 REST API
=============
创建/查看/删除分享链接，访问共享会话内容。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.auth import get_user_from_request
from core.share import (
    create_share_link,
    get_share_by_token,
    validate_share_access,
    get_shared_session_data,
    list_share_links,
    delete_share_link,
)

logger = logging.getLogger("agent_skills.share.routes")


async def api_create_share(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/share — 创建分享链接"""
    session_id = request.path_params["id"]
    user = get_user_from_request(request)
    user_id = user["user_id"] if user else ""

    try:
        body = await request.json()
    except Exception:
        body = {}

    expires_hours = body.get("expires_hours", 0)
    password = body.get("password", "")

    result = create_share_link(
        session_id=session_id,
        user_id=user_id,
        expires_hours=expires_hours,
        password=password,
    )
    if not result["success"]:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


async def api_list_shares(request: Request) -> JSONResponse:
    """GET /api/chat/sessions/{id}/shares — 列出会话的分享链接"""
    session_id = request.path_params["id"]
    links = list_share_links(session_id)
    return JSONResponse({"success": True, "shares": links})


async def api_delete_share(request: Request) -> JSONResponse:
    """DELETE /api/share/{share_id} — 删除分享链接"""
    share_id = request.path_params["share_id"]
    user = get_user_from_request(request)
    user_id = user["user_id"] if user else ""
    ok = delete_share_link(share_id, user_id)
    if not ok:
        return JSONResponse({"success": False, "message": "链接不存在"}, status_code=404)
    return JSONResponse({"success": True})


async def api_view_share(request: Request) -> JSONResponse:
    """
    GET /api/share/{token} — 查看分享内容（只读）
    POST /api/share/{token} — 带密码访问
    """
    token = request.path_params["token"]
    share = get_share_by_token(token)
    if not share:
        return JSONResponse(
            {"success": False, "message": "分享链接不存在或已失效"}, status_code=404
        )

    # 获取密码（POST 请求体或 query 参数）
    password = ""
    if request.method == "POST":
        try:
            body = await request.json()
            password = body.get("password", "")
        except Exception:
            pass
    else:
        password = request.query_params.get("password", "")

    # 验证访问权限
    access = validate_share_access(share, password)
    if not access["valid"]:
        status = 403 if "need_password" not in access else 401
        return JSONResponse(
            {"success": False, **access}, status_code=status
        )

    # 获取会话数据
    data = get_shared_session_data(share)
    if not data:
        return JSONResponse(
            {"success": False, "message": "原始会话已被删除"}, status_code=404
        )

    return JSONResponse({
        "success": True,
        "share": {
            "token": share["token"],
            "expires_at": share.get("expires_at"),
            "view_count": share.get("view_count", 0) + 1,
        },
        **data,
    })


share_routes = [
    Route("/api/chat/sessions/{id}/share", api_create_share, methods=["POST"]),
    Route("/api/chat/sessions/{id}/shares", api_list_shares, methods=["GET"]),
    Route("/api/share/{share_id}", api_delete_share, methods=["DELETE"]),
    Route("/api/share/{token}", api_view_share, methods=["GET", "POST"]),
]
