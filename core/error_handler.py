"""
统一错误处理中间件
=================
捕获所有未处理的异常，返回统一的 JSON 错误格式。
避免内部错误信息泄露给客户端。
"""

import logging
import traceback

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("agent_skills.error_handler")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    全局异常捕获中间件。

    所有未被路由处理函数捕获的异常都会被拦截，
    返回统一的 JSON 格式错误响应：

        {
            "success": false,
            "error": "错误类型",
            "message": "用户友好的错误描述",
            "detail": "调试信息（仅 DEBUG 模式）"
        }
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except ValueError as exc:
            logger.warning("请求参数错误 [%s %s]: %s", request.method, request.url.path, exc)
            return JSONResponse(
                {
                    "success": False,
                    "error": "bad_request",
                    "message": str(exc),
                },
                status_code=400,
            )
        except FileNotFoundError as exc:
            logger.warning("资源不存在 [%s %s]: %s", request.method, request.url.path, exc)
            return JSONResponse(
                {
                    "success": False,
                    "error": "not_found",
                    "message": "请求的资源不存在",
                },
                status_code=404,
            )
        except Exception as exc:
            logger.exception(
                "未处理异常 [%s %s]: %s", request.method, request.url.path, exc
            )
            # 生产环境不暴露堆栈，仅返回通用提示
            import os
            debug = os.environ.get("DEBUG", "false").lower() == "true"
            body = {
                "success": False,
                "error": "internal_error",
                "message": "服务内部错误，请稍后重试",
            }
            if debug:
                body["detail"] = traceback.format_exc()

            return JSONResponse(body, status_code=500)
