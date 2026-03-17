"""
模板市场 REST API
=================
模板的列表、详情与使用计数。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.templates import list_templates, get_template, increment_template_use

logger = logging.getLogger("agent_skills.template_routes")


async def api_list_templates(request: Request) -> JSONResponse:
    """GET /api/templates — 列出模板（支持 ?category= 过滤）"""
    category = request.query_params.get("category", "")
    templates = list_templates(category)
    return JSONResponse({"success": True, "templates": templates})


async def api_get_template(request: Request) -> JSONResponse:
    """GET /api/templates/{id} — 获取单个模板"""
    template_id = request.path_params["id"]
    tpl = get_template(template_id)
    if not tpl:
        return JSONResponse({"success": False, "message": "模板不存在"}, status_code=404)
    return JSONResponse({"success": True, "template": tpl})


async def api_use_template(request: Request) -> JSONResponse:
    """POST /api/templates/{id}/use — 使用模板（计数+1，返回模板内容）"""
    template_id = request.path_params["id"]
    tpl = get_template(template_id)
    if not tpl:
        return JSONResponse({"success": False, "message": "模板不存在"}, status_code=404)
    increment_template_use(template_id)
    # 重新获取更新后的计数
    tpl = get_template(template_id)
    return JSONResponse({"success": True, "template": tpl})


template_routes = [
    Route("/api/templates", api_list_templates, methods=["GET"]),
    Route("/api/templates/{id}", api_get_template, methods=["GET"]),
    Route("/api/templates/{id}/use", api_use_template, methods=["POST"]),
]
