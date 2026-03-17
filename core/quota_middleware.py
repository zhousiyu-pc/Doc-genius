"""
配额管控中间件
=============
拦截需要配额检查的 API 请求，超限返回 403。
成功响应后才记录用量。
"""

import re
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.auth import get_user_from_request
from core.plans import check_quota, record_usage

logger = logging.getLogger("agent_skills.quota")

# 路径 → action 映射
_QUOTA_ROUTES = [
    (re.compile(r"^/api/chat/sessions/[^/]+/messages$"), "chat",
     "今日对话次数已达上限，请升级套餐"),
    (re.compile(r"^/api/chat/sessions/[^/]+/confirm$"), "doc",
     "本月文档生成次数已达上限，请升级套餐"),
    (re.compile(r"^/api/chat/sessions/[^/]+/upload$"), "upload",
     "本月上传次数已达上限，请升级套餐"),
]


class QuotaMiddleware(BaseHTTPMiddleware):
    """
    配额检查中间件。

    - 仅拦截 POST 请求中匹配的路径
    - 匿名用户按 free 套餐处理（user_id = 'anonymous'）
    - 超限返回 403
    - 响应成功（2xx）后才记录用量
    """

    async def dispatch(self, request: Request, call_next):
        # 仅检查 POST 请求
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        matched_action = None
        matched_message = None

        for pattern, action, message in _QUOTA_ROUTES:
            if pattern.match(path):
                matched_action = action
                matched_message = message
                break

        if matched_action is None:
            return await call_next(request)

        # 提取用户身份
        user = get_user_from_request(request)
        user_id = user["user_id"] if user else "anonymous"

        # 检查配额
        quota = check_quota(user_id, matched_action)
        if not quota["allowed"]:
            logger.info(
                "配额超限: user=%s, action=%s, used=%d, limit=%d",
                user_id, matched_action, quota["used"], quota["limit"],
            )
            return JSONResponse(
                {
                    "success": False,
                    "error": "quota_exceeded",
                    "message": matched_message,
                    "quota": quota,
                },
                status_code=403,
            )

        # 放行请求
        response = await call_next(request)

        # 仅在成功响应时记录用量
        if 200 <= response.status_code < 300:
            try:
                record_usage(user_id, matched_action)
            except Exception as exc:
                logger.error("记录用量失败: user=%s, action=%s, error=%s",
                             user_id, matched_action, exc)

        return response
