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

import os
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.routing import Route

from skills.export_utils import get_export_dir

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
            elif evt_type == "export":
                # 推送导出事件给前端，由前端进入消息选择模式
                export_info = event.get("data", {})
                content_type = export_info.get("content_type", "chat")
                if content_type in ("outline", "detail", "proposal_ppt"):
                    # 标准文档类型：直接启动后台 pipeline
                    data = json.dumps(export_info, ensure_ascii=False)
                    yield f"event: export\ndata: {data}\n\n"
                    try:
                        from skills.pipeline import run_adhoc_export_async
                        asyncio.ensure_future(
                            run_adhoc_export_async(
                                session_id,
                                export_info.get("format", "docx"),
                                content_type,
                            )
                        )
                    except Exception as export_exc:
                        logger.exception("启动即时导出失败: %s", export_exc)
                else:
                    # chat 类型：推送事件给前端，让用户选择要导出的消息
                    data = json.dumps(export_info, ensure_ascii=False)
                    yield f"event: export\ndata: {data}\n\n"
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
    响应: SSE 流，包含 text / outline / export / done 等事件类型。
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

    # 优先在路由层识别“生成 Word/PDF/PPT”等控制指令，避免再调用 LLM 回复一段无关文案。
    from core.conversation import detect_export_intent_from_user, save_message

    export_info = detect_export_intent_from_user(content)

    if export_info:
        # 保存用户这条控制指令，但不调用 LLM。
        save_message(session_id, "user", content)

        async def _export_only_sse() -> AsyncGenerator[str, None]:
            """
            仅推送 export 事件和 done 事件的 SSE 流，不返回任何文本回复。
            """
            content_type = export_info.get("content_type", "chat")
            fmt = export_info.get("format", "docx")

            # 标准文档类型：直接在后端启动文档生成
            if content_type in ("outline", "detail", "proposal_ppt"):
                data = json.dumps(export_info, ensure_ascii=False)
                yield f"event: export\ndata: {data}\n\n"
                try:
                    from skills.pipeline import run_adhoc_export_async

                    asyncio.ensure_future(
                        run_adhoc_export_async(session_id, fmt, content_type)
                    )
                except Exception as exc:
                    logger.exception("启动即时导出失败: %s", exc)
            else:
                # chat 类型：只通知前端进入“消息选择导出”模式
                data = json.dumps(export_info, ensure_ascii=False)
                yield f"event: export\ndata: {data}\n\n"

            # 无论哪种情况，都以 done 结束 SSE 流
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            _export_only_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 普通对话：走原有 LLM 流式逻辑
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
    
    请求体（可选）: {"doc_types": ["outline", "detail", "proposal_ppt"]}
    - outline: 需求大纲（精简）
    - detail: 需求详细设计（完整5件套）
    - proposal_ppt: 需求立项报告
    默认 ["detail"]。
    """
    session_id = request.path_params["id"]
    result = confirm_outline(session_id)

    if not result.get("success"):
        return JSONResponse(result, status_code=400)

    # 解析用户选择的文档配置
    try:
        body = await request.json()
    except Exception:
        body = {}
    doc_configs = body.get("doc_configs")
    if not doc_configs:
        # 兼容旧格式或无参数
        doc_types = body.get("doc_types") or ["detail"]
        doc_configs = {dt: [] for dt in doc_types}

    try:
        from skills.pipeline import run_pipeline_async
        outline = result["outline"]
        asyncio.ensure_future(
            run_pipeline_async(session_id, outline, doc_configs)
        )
    except ImportError:
        logger.warning("Skill Pipeline 模块尚未加载")
    except Exception as exc:
        logger.exception("启动 Skill Pipeline 失败: %s", exc)

    return JSONResponse({
        "success": True,
        "message": "已确认需求大纲，文档生成已启动",
        "outline": result["outline"],
        "doc_configs": doc_configs,
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


async def api_export_selected(request: Request) -> JSONResponse:
    """
    POST /api/chat/sessions/{id}/export — 导出用户选中的消息内容。

    请求体: {
        "format": "docx" | "pdf" | "pptx",
        "message_ids": ["msg_id_1", "msg_id_2", ...]
    }
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

    export_format = body.get("format", "docx")
    message_ids = body.get("message_ids", [])

    if export_format not in ("docx", "pdf", "pptx"):
        return JSONResponse(
            {"success": False, "message": "不支持的导出格式"}, status_code=400
        )
    if not message_ids or not isinstance(message_ids, list):
        return JSONResponse(
            {"success": False, "message": "请选择至少一条消息"}, status_code=400
        )

    try:
        from skills.pipeline import run_selected_export_async
        asyncio.ensure_future(
            run_selected_export_async(session_id, export_format, message_ids)
        )
    except Exception as exc:
        logger.exception("启动选择导出失败: %s", exc)
        return JSONResponse(
            {"success": False, "message": f"启动失败: {exc}"}, status_code=500
        )

    return JSONResponse({
        "success": True,
        "message": f"已启动导出，共 {len(message_ids)} 条消息",
    })


async def api_download_file(request: Request):
    """GET /api/chat/sessions/{id}/files/{filename} — 下载会话导出文件（PDF/Word/PPT）"""
    from urllib.parse import quote

    session_id = request.path_params["id"]
    filename = request.path_params.get("filename", "").strip()
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"success": False, "message": "非法文件名"}, status_code=400)
    session = get_session(session_id)
    if not session:
        return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)
    export_dir = get_export_dir(session_id)
    file_path = os.path.join(export_dir, filename)
    if not os.path.abspath(file_path).startswith(os.path.abspath(export_dir)):
        return JSONResponse({"success": False, "message": "非法路径"}, status_code=400)
    if not os.path.isfile(file_path):
        logger.warning("请求下载的文件不存在: %s", file_path)
        return JSONResponse({"success": False, "message": "文件不存在"}, status_code=404)

    # RFC 5987 编码，确保中文文件名在浏览器中正确显示
    encoded_filename = quote(filename, safe="")
    content_disposition = (
        f'attachment; filename="{encoded_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": content_disposition},
    )


routes = [
    Route("/api/chat/sessions", api_sessions_handler, methods=["GET", "POST"]),
    Route("/api/chat/sessions/{id}", api_session_handler, methods=["GET", "DELETE"]),
    Route("/api/chat/sessions/{id}/messages", api_send_message, methods=["POST"]),
    Route("/api/chat/sessions/{id}/confirm", api_confirm_outline, methods=["POST"]),
    Route("/api/chat/sessions/{id}/export", api_export_selected, methods=["POST"]),
    Route("/api/chat/sessions/{id}/files/{filename:path}", api_download_file, methods=["GET"]),
]
