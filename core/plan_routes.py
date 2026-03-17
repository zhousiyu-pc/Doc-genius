"""
套餐 REST API
=============
套餐列表、用户套餐查询、用量查询。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.auth import get_user_from_request
from core.plans import list_plans, get_user_plan, get_user_usage

logger = logging.getLogger("agent_skills.plan_routes")


async def api_list_plans(request: Request) -> JSONResponse:
    """GET /api/plans — 列出所有活跃套餐（公开）"""
    plans = list_plans()
    return JSONResponse({"success": True, "plans": plans})


async def api_user_plan(request: Request) -> JSONResponse:
    """GET /api/user/plan — 获取当前用户套餐+用量"""
    user = get_user_from_request(request)
    user_id = user["user_id"] if user else "anonymous"
    result = get_user_plan(user_id)
    return JSONResponse({"success": True, **result})


async def api_user_usage(request: Request) -> JSONResponse:
    """GET /api/user/usage — 获取用户用量详情"""
    user = get_user_from_request(request)
    user_id = user["user_id"] if user else "anonymous"
    usage = get_user_usage(user_id)
    return JSONResponse({"success": True, "usage": usage})


plan_routes = [
    Route("/api/plans", api_list_plans, methods=["GET"]),
    Route("/api/user/plan", api_user_plan, methods=["GET"]),
    Route("/api/user/usage", api_user_usage, methods=["GET"]),
]
