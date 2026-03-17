"""
认证 REST API
=============
用户注册、登录、获取当前用户信息。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.auth import register_user, login_user, get_user_from_request

logger = logging.getLogger("agent_skills.auth.routes")


async def api_register(request: Request) -> JSONResponse:
    """POST /api/auth/register — 用户注册"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "message": "请求体格式错误"}, status_code=400)

    username = body.get("username", "")
    password = body.get("password", "")
    result = register_user(username, password)

    if not result["success"]:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


async def api_login(request: Request) -> JSONResponse:
    """POST /api/auth/login — 用户登录"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "message": "请求体格式错误"}, status_code=400)

    username = body.get("username", "")
    password = body.get("password", "")
    result = login_user(username, password)

    if not result["success"]:
        return JSONResponse(result, status_code=401)
    return JSONResponse(result)


async def api_me(request: Request) -> JSONResponse:
    """GET /api/auth/me — 获取当前用户信息"""
    user = get_user_from_request(request)
    if not user:
        return JSONResponse({"success": False, "message": "未登录"}, status_code=401)
    return JSONResponse({"success": True, **user})


auth_routes = [
    Route("/api/auth/register", api_register, methods=["POST"]),
    Route("/api/auth/login", api_login, methods=["POST"]),
    Route("/api/auth/me", api_me, methods=["GET"]),
]
