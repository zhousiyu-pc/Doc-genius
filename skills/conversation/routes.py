"""
对话管理 REST API
================
提供多轮对话式需求分析的 HTTP 接口。
消息发送接口返回 SSE（Server-Sent Events）流，实现实时推送。
支持 JWT 认证和用户会话隔离（通过 AUTH_REQUIRED 环境变量控制）。
"""

import os
import json
import logging
import asyncio
from typing import AsyncGenerator

from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.routing import Route

from skills.export_utils import get_export_dir
from core.auth import get_user_from_request

from core.conversation import (
    create_session,
    get_session,
    list_sessions,
    search_sessions,
    delete_session,
    get_messages,
    get_stage_summaries,
    chat_stream,
    confirm_outline,
    update_session,
    advance_stage,
)

logger = logging.getLogger("agent_skills.conversation.routes")

# 是否强制要求认证（设为 true 后所有对话 API 需要 Bearer token）
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "false").lower() == "true"


def _get_user_id(request: Request) -> str:
    """
    从请求中提取 user_id。
    AUTH_REQUIRED=true 时强制认证；否则返回空字符串（兼容匿名模式）。
    """
    user = get_user_from_request(request)
    if user:
        return user["user_id"]
    return ""


def _require_auth(request: Request):
    """
    认证守卫：AUTH_REQUIRED=true 时检查 token，无效则返回 401。
    返回 (user_id, error_response)。
    """
    user = get_user_from_request(request)
    if AUTH_REQUIRED and not user:
        return "", JSONResponse(
            {"success": False, "message": "请先登录"}, status_code=401
        )
    return (user["user_id"] if user else ""), None


def _check_session_access(session: dict, user_id: str):
    """检查用户是否有权访问该会话。"""
    if not AUTH_REQUIRED or not user_id:
        return None  # 匿名模式不检查
    session_owner = session.get("user_id", "")
    if session_owner and session_owner != user_id:
        return JSONResponse(
            {"success": False, "message": "无权访问此会话"}, status_code=403
        )
    return None


async def api_create_session(request: Request) -> JSONResponse:
    """POST /api/chat/sessions — 创建新对话会话"""
    user_id, err = _require_auth(request)
    if err:
        return err
    try:
        body = await request.json()
    except Exception:
        body = {}
    title = body.get("title", "")
    mode = body.get("mode", "free")
    model = body.get("model")  # 可选，None 则使用默认
    
    # 检查模型访问权限
    if model:
        from core.plans import check_model_access
        if not check_model_access(user_id or "anonymous", model):
            return JSONResponse(
                {"success": False, "message": "当前套餐无权使用此模型，请升级套餐", "required_plan": "pro"},
                status_code=403
            )
    
    session = create_session(title, mode, user_id=user_id, model=model)
    return JSONResponse({"success": True, **session})


async def api_update_session_stage(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/stage — 手动更新会话阶段"""
    session_id = request.path_params["id"]
    try:
        body = await request.json()
    except:
        return JSONResponse({"success": False, "message": "无效的请求体"}, status_code=400)
    
    new_stage = body.get("stage")
    if not new_stage:
        return JSONResponse({"success": False, "message": "未指定阶段"}, status_code=400)
    
    update_session(session_id, current_stage=new_stage)
    return JSONResponse({"success": True, "stage": new_stage})


async def api_get_stage_summaries(request: Request) -> JSONResponse:
    """GET /api/chat/sessions/{id}/stage_summaries — 获取敏捷模式各环节成果摘要"""
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )
    if session.get("mode") != "agile":
        return JSONResponse(
            {"success": True, "summaries": []},
        )
    summaries = get_stage_summaries(session_id)
    return JSONResponse({"success": True, "summaries": summaries})


async def api_advance_stage(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/advance_stage — 用户确认进入下一环节"""
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )
    if session.get("mode") != "agile":
        return JSONResponse(
            {"success": False, "message": "仅敏捷模式支持"}, status_code=400
        )
    result = advance_stage(session_id)
    if not result:
        return JSONResponse(
            {"success": False, "message": "已是最后一环节或无法切换"}, status_code=400
        )
    return JSONResponse({"success": True, **result})


async def api_export_stage(request: Request) -> JSONResponse:
    """POST /api/chat/sessions/{id}/export_stage — 按环节导出附件"""
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
            {"success": False, "message": "无效的请求体"}, status_code=400
        )
    stage_id = body.get("stage")
    export_format = body.get("format", "docx")
    if not stage_id:
        return JSONResponse(
            {"success": False, "message": "未指定环节"}, status_code=400
        )
    if export_format not in ("docx", "pdf", "pptx"):
        return JSONResponse(
            {"success": False, "message": "不支持的格式"}, status_code=400
        )
    try:
        from skills.pipeline import run_stage_export_async
        asyncio.ensure_future(
            run_stage_export_async(session_id, stage_id, export_format)
        )
    except Exception as exc:
        logger.exception("启动环节导出失败: %s", exc)
        return JSONResponse(
            {"success": False, "message": str(exc)}, status_code=500
        )
    return JSONResponse({
        "success": True,
        "message": f"已启动环节导出（{export_format}）",
    })


async def api_rename_session(request: Request) -> JSONResponse:
    """
    PUT /api/chat/sessions/{id}/rename — 重命名会话标题。

    请求体: {"title": "新标题"}
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
            {"success": False, "message": "无效的请求体"}, status_code=400
        )

    new_title = body.get("title", "").strip()
    if not new_title:
        return JSONResponse(
            {"success": False, "message": "标题不能为空"}, status_code=400
        )
    if len(new_title) > 100:
        new_title = new_title[:100]

    update_session(session_id, title=new_title)
    return JSONResponse({"success": True, "title": new_title})


async def api_list_sessions(request: Request) -> JSONResponse:
    """GET /api/chat/sessions — 列出所有对话会话（支持 ?q= 搜索）"""
    user_id = _get_user_id(request)
    query = request.query_params.get("q", "").strip()
    if query:
        sessions = search_sessions(query, user_id=user_id)
    else:
        sessions = list_sessions(user_id=user_id)
    return JSONResponse({"success": True, "sessions": sessions})


async def api_get_session(request: Request) -> JSONResponse:
    """GET /api/chat/sessions/{id} — 获取会话详情及消息历史"""
    user_id, err = _require_auth(request)
    if err:
        return err
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )
    access_err = _check_session_access(session, user_id)
    if access_err:
        return access_err
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
            elif evt_type == "stage_update":
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: stage_update\ndata: {data}\n\n"
            elif evt_type == "stage_ready":
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: stage_ready\ndata: {data}\n\n"
            elif evt_type == "stage_advance":
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: stage_advance\ndata: {data}\n\n"
            elif evt_type == "milestone":
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: milestone\ndata: {data}\n\n"
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



# ── 文件上传安全配置 ──────────────────────────────

# 允许上传的文件扩展名白名单
ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".docx", ".pdf", ".html",
    ".py", ".java", ".js", ".ts", ".sql", ".log",
}

# 每用户每小时最多上传文件数
UPLOAD_RATE_LIMIT_PER_HOUR = 20

# 上传频率计数器：key -> (count, window_start)
import threading as _threading
import time as _time

_upload_counter_lock = _threading.Lock()
_upload_counters: dict[str, tuple[int, float]] = {}


def _check_upload_rate(key: str) -> bool:
    """
    检查上传频率。返回 True 表示允许，False 表示超限。
    使用滑动窗口：每小时 UPLOAD_RATE_LIMIT_PER_HOUR 次。
    """
    now = _time.time()
    window = 3600  # 1 小时

    with _upload_counter_lock:
        if key in _upload_counters:
            count, window_start = _upload_counters[key]
            if now - window_start > window:
                # 窗口过期，重置
                _upload_counters[key] = (1, now)
                return True
            if count >= UPLOAD_RATE_LIMIT_PER_HOUR:
                return False
            _upload_counters[key] = (count + 1, window_start)
            return True
        else:
            _upload_counters[key] = (1, now)
            return True


def _get_upload_rate_key(request: Request) -> str:
    """获取上传频率限制的 key（优先 user_id，回退到 IP）。"""
    user = get_user_from_request(request)
    if user and user.get("user_id"):
        return f"user:{user['user_id']}"
    # 回退到 IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return f"ip:{real_ip.strip()}"
    if request.client:
        return f"ip:{request.client.host}"
    return "ip:unknown"


async def api_upload_file(request: Request) -> JSONResponse:
    """
    POST /api/chat/sessions/{id}/upload — 上传文件并提取文本内容。

    接受 multipart/form-data 格式的文件上传。
    将文件内容提取为文本，保存为 msg_type='file' 的消息，
    文件文本内容会自动纳入后续 LLM 对话上下文。

    安全限制:
        - 文件大小：最大 10MB
        - 扩展名白名单：.txt .md .csv .json .xml .yaml .yml .docx .pdf .html .py .java .js .ts .sql .log
        - 上传频率：每用户每小时最多 20 个文件

    表单字段:
        - file: 上传的文件
        - message: (可选) 用户对文件的说明或指令

    Returns:
        JSON 包含消息 ID、文件名、提取的文本预览等信息
    """
    session_id = request.path_params["id"]
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            {"success": False, "message": "会话不存在"}, status_code=404
        )

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse(
            {"success": False, "message": "请使用 multipart/form-data 格式上传文件"},
            status_code=400,
        )

    form = await request.form()
    upload_file = form.get("file")
    user_message = form.get("message", "")

    if not upload_file or not hasattr(upload_file, "read"):
        return JSONResponse(
            {"success": False, "message": "未找到上传文件"}, status_code=400
        )

    filename = getattr(upload_file, "filename", "unknown")

    # ── 扩展名白名单检查 ──
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed_list = " ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        return JSONResponse(
            {
                "success": False,
                "message": f"不支持的文件类型 '{ext}'，允许的类型: {allowed_list}",
            },
            status_code=400,
        )

    # ── 上传频率检查 ──
    rate_key = _get_upload_rate_key(request)
    if not _check_upload_rate(rate_key):
        return JSONResponse(
            {
                "success": False,
                "message": f"上传过于频繁，每小时最多上传 {UPLOAD_RATE_LIMIT_PER_HOUR} 个文件",
            },
            status_code=400,
        )

    file_bytes = await upload_file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        return JSONResponse(
            {"success": False, "message": "文件为空"}, status_code=400
        )

    from core.file_reader import extract_text, get_file_type_label, MAX_FILE_SIZE
    from core.conversation import save_message

    if file_size > MAX_FILE_SIZE:
        return JSONResponse(
            {"success": False, "message": f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024} MB）"},
            status_code=400,
        )

    extracted_text, error = extract_text(file_bytes, filename)
    if error:
        return JSONResponse(
            {"success": False, "message": f"文件读取失败: {error}"}, status_code=400
        )

    file_type_label = get_file_type_label(filename)

    # 保存文件消息：角色为 user，类型为 file
    file_metadata = {
        "filename": filename,
        "file_size": file_size,
        "file_type": file_type_label,
        "char_count": len(extracted_text),
    }
    msg_id = save_message(
        session_id,
        "user",
        extracted_text,
        msg_type="file",
        metadata=file_metadata,
    )

    # 如果用户附带了说明文字，额外保存一条文本消息
    user_msg_id = None
    if isinstance(user_message, str) and user_message.strip():
        user_msg_id = save_message(session_id, "user", user_message.strip())

    logger.info(
        "文件上传成功: session=%s, file=%s, size=%d, chars=%d",
        session_id, filename, file_size, len(extracted_text),
    )

    preview = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")

    return JSONResponse({
        "success": True,
        "message": "文件上传成功",
        "file_msg_id": msg_id,
        "user_msg_id": user_msg_id,
        "filename": filename,
        "file_size": file_size,
        "file_type": file_type_label,
        "char_count": len(extracted_text),
        "preview": preview,
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



async def api_list_models(request: Request) -> JSONResponse:
    """GET /api/models — 获取可用模型列表（带权限过滤）"""
    user_id = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from core.auth import verify_token
        payload = verify_token(auth_header[7:])
        if payload:
            user_id = payload["sub"]
    
    from core.config import AVAILABLE_MODELS
    from core.plans import get_user_plan
    
    user_plan = get_user_plan(user_id or "anonymous")
    plan_id = user_plan["plan"]["id"]
    
    from core.config import PLAN_MODEL_ACCESS
    allowed_tiers = PLAN_MODEL_ACCESS.get(plan_id, ["base"])
    
    # 过滤用户有权访问的模型
    accessible_models = [
        m for m in AVAILABLE_MODELS
        if m["tier"] in allowed_tiers
    ]
    
    return JSONResponse({
        "success": True,
        "models": accessible_models,
        "current_plan": plan_id,
    })


async def api_switch_model(request: Request) -> JSONResponse:
    """PUT /api/chat/sessions/{id}/model — 切换会话使用的模型"""
    from core.plans import check_model_access
    
    session_id = request.path_params["id"]
    user_id, err = _require_auth(request)
    if err:
        return err
    
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "message": "无效的请求体"}, status_code=400)
    
    model = body.get("model")
    if not model:
        return JSONResponse({"success": False, "message": "未指定模型"}, status_code=400)
    
    # 检查模型访问权限
    if not check_model_access(user_id or "anonymous", model):
        return JSONResponse(
            {"success": False, "message": "当前套餐无权使用此模型，请升级套餐", "required_plan": "pro"},
            status_code=403
        )
    
    # 更新会话的模型设置
    with get_db() as conn:
        conn.execute(
            "UPDATE chat_sessions SET model = ? WHERE id = ? AND user_id = ?",
            (model, session_id, user_id),
        )
        if conn.rowcount == 0:
            return JSONResponse({"success": False, "message": "会话不存在"}, status_code=404)
    
    logger.info("切换模型：session=%s, model=%s", session_id, model)
    return JSONResponse({"success": True, "model": model})



routes = [
    Route("/api/chat/sessions", api_sessions_handler, methods=["GET", "POST"]),
    Route("/api/chat/sessions/{id}", api_session_handler, methods=["GET", "DELETE"]),
    Route("/api/chat/sessions/{id}/messages", api_send_message, methods=["POST"]),
    Route("/api/chat/sessions/{id}/confirm", api_confirm_outline, methods=["POST"]),
    Route("/api/chat/sessions/{id}/upload", api_upload_file, methods=["POST"]),
    Route("/api/chat/sessions/{id}/stage", api_update_session_stage, methods=["POST"]),
    Route("/api/chat/sessions/{id}/stage_summaries", api_get_stage_summaries, methods=["GET"]),
    Route("/api/chat/sessions/{id}/advance_stage", api_advance_stage, methods=["POST"]),
    Route("/api/chat/sessions/{id}/export_stage", api_export_stage, methods=["POST"]),
    Route("/api/chat/sessions/{id}/rename", api_rename_session, methods=["PUT"]),
    Route("/api/chat/sessions/{id}/export", api_export_selected, methods=["POST"]),
    Route("/api/chat/sessions/{id}/files/{filename:path}", api_download_file, methods=["GET"]),
    Route("/api/chat/sessions/{id}/model", api_switch_model, methods=["PUT"]),
    Route("/api/models", api_list_models, methods=["GET"]),
]
