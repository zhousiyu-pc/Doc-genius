"""
对话管理 REST API
================
提供多轮对话式需求分析的 HTTP 接口。
消息发送接口返回 SSE（Server-Sent Events）流，实现实时推送。
"""

import json
import logging
import asyncio
from typing import AsyncGenerator

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.responses import StreamingResponse

from core.conversation import (
    create_session,
    get_session,
    list_sessions,
    delete_session,
    get_messages,
    chat_stream,
    confirm_outline,
    update_session,
)

logger = logging.getLogger("agent_skills.conversation.routes")


async def api_create_session(request: Request) -> JSONResponse:
    """POST /api/chat/sessions — 创建新对话会话"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    title = body.get("title", "")
    session = create_session(title)
    return JSONResponse({"success": True, **session})


async def api_list_sessions(request: Request) -> JSONResponse:
    """GET /api/chat/sessions — 列出所有对话会话"""
    sessions = list_sessions()
    return JSONResponse({"success": True, "sessions": sessions})


async def api_get_session(request: Request) -> JSONResponse:
    """GET /api/chat/sessions/{id} — 获取会话详情及消息历史"""
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )
    messages = get_messages(session_id)
    # 解析 outline 字段
    outline = None
    if session.get("outline"):
        try:
            outline = json.loads(session["outline"])
        except (json.JSONDecodeError, TypeError):
            outline = None
    return JSONResponse({
        "success": True,
        "session": {**session, "outline": outline},
        "messages": messages,
    })


async def api_delete_session(request: Request) -> JSONResponse:
    """DELETE /api/chat/sessions/{id} — 删除会话"""
    session_id = request.path_params["id"]
    deleted = delete_session(session_id)
    if not deleted:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )
    return JSONResponse({"success": True, "message": "会话已删除"})


async def _sse_generator(session_id: str, content: str) -> AsyncGenerator[str, None]:
    """
    将同步的 chat_stream 生成器包装为异步 SSE 生成器。
    每个事件格式为 "event: {type}\ndata: {json}\n\n"。
    """
    loop = asyncio.get_event_loop()

    def _sync_stream():
        """在同步上下文中收集所有事件，避免线程安全问题。"""
        return list(chat_stream(session_id, content))

    try:
        events = await loop.run_in_executor(None, _sync_stream)
        for event in events:
            evt_type = event.get("type", "text")
            if evt_type == "text":
                data = json.dumps({"content": event["content"]}, ensure_ascii=False)
                yield f"event: text\ndata: {data}\n\n"
            elif evt_type == "outline":
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: outline\ndata: {data}\n\n"
            elif evt_type == "done":
                yield "event: done\ndata: {}\n\n"
    except Exception as exc:
        logger.exception("SSE 流生成失败: %s", exc)
        error_data = json.dumps(
            {"content": f"服务异常: {exc}"}, ensure_ascii=False
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "event: done\ndata: {}\n\n"


async def api_send_message(request: Request) -> StreamingResponse:
    """
    POST /api/chat/sessions/{id}/messages — 发送用户消息并返回 SSE 流。
    
    请求体: {"content": "用户输入的文本"}
    响应: SSE 流，包含 text / outline / done 三种事件类型。
    """
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "message": "请求体格式错误"}, status_code=400
        )

    content = body.get("content", "").strip()
    if not content:
        return JSONResponse(
            {"success": False, "message": "消息内容不能为空"}, status_code=400
        )

    return StreamingResponse(
        _sse_generator(session_id, content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def api_confirm_outline(request: Request) -> JSONResponse:
    """
    POST /api/chat/sessions/{id}/confirm — 用户确认需求大纲，启动 Skill 流水线。
    
    确认后会话状态变为 confirmed，然后异步启动文档生成流水线。
    """
    session_id = request.path_params["id"]
    result = confirm_outline(session_id)

    if not result.get("success"):
        return JSONResponse(result, status_code=400)

    # 异步启动 Skill Pipeline
    try:
        from skills.pipeline import run_pipeline_async
        outline = result["outline"]
        asyncio.ensure_future(
            run_pipeline_async(session_id, outline)
        )
    except ImportError:
        logger.warning("Skill Pipeline 模块尚未加载")
    except Exception as exc:
        logger.exception("启动 Skill Pipeline 失败: %s", exc)

    return JSONResponse({
        "success": True,
        "message": "已确认需求大纲，文档生成已启动",
        "outline": result["outline"],
    })


async def api_session_handler(request: Request):
    """路由分发：根据 HTTP 方法处理 /api/chat/sessions/{id}"""
    if request.method == "GET":
        return await api_get_session(request)
    elif request.method == "DELETE":
        return await api_delete_session(request)
    return JSONResponse({"error": "Method not allowed"}, status_code=405)


async def api_sessions_handler(request: Request):
    """路由分发：根据 HTTP 方法处理 /api/chat/sessions"""
    if request.method == "GET":
        return await api_list_sessions(request)
    elif request.method == "POST":
        return await api_create_session(request)
    return JSONResponse({"error": "Method not allowed"}, status_code=405)


routes = [
    Route("/api/chat/sessions", api_sessions_handler, methods=["GET", "POST"]),
    Route("/api/chat/sessions/{id}", api_session_handler, methods=["GET", "DELETE"]),
    Route("/api/chat/sessions/{id}/messages", api_send_message, methods=["POST"]),
    Route("/api/chat/sessions/{id}/confirm", api_confirm_outline, methods=["POST"]),
]
