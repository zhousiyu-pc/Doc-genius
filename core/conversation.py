"""
对话引擎 — LLM 多轮对话式需求分析
================================
通过自然对话理解用户意图，逐步澄清需求，
当信息充分时自动输出结构化的需求大纲。

核心职责：
- 管理对话历史，构建发给 LLM 的 messages 数组
- 解析 LLM 回复中的 [OUTLINE] 标记，提取结构化大纲
- 提供会话的 CRUD 和消息持久化
"""

import json
import re
import uuid
import logging
import datetime
from dataclasses import dataclass, field
from typing import Optional, Generator

from .db import get_db
from .llm_client import call_chat_stream, call_chat

logger = logging.getLogger("agent_skills.conversation")

# ── 需求分析师 System Prompt ──────────────────────────────────────

CONVERSATION_SYSTEM_PROMPT = """你是一位资深的产品需求分析师，拥有丰富的软件产品设计和架构经验。
你的任务是通过自然、友好的对话，帮助用户精准定义他们的软件产品需求。

## 对话策略

1. **先理解大方向**：用户想做什么产品/系统？解决什么问题？服务哪个行业？
2. **逐步追问关键信息**（每次只问 1-2 个最重要的问题，不要一次问太多）：
   - 目标用户群体是谁？
   - 核心业务流程是怎样的？
   - 最重要的 3-5 个功能是什么？
   - 有哪些技术或业务约束？
   - 是否需要与现有系统集成？
3. **主动补充专业建议**：根据你的行业经验，帮用户想到他们可能遗漏的重要功能或考虑点。
4. **确认理解**：在输出大纲前，先用一两句话总结你的理解，让用户确认。

## 对话风格

- 专业但亲切，避免过多技术术语
- 回复简洁有条理，用分点列出关键信息
- 积极引导用户思考，而不是被动等待

## 信息充分的判断标准

当以下信息已基本明确时，你就可以输出需求大纲了：
- 已明确产品类型和所属行业/领域
- 已明确至少一类核心目标用户
- 已明确 3 个以上核心功能模块
- 已了解基本业务模式或使用场景

## 输出大纲的格式要求

当你认为信息已经充分，准备输出需求大纲时：
1. 先用自然语言总结你的理解
2. 然后在回复末尾，以如下格式附加结构化大纲（必须严格遵循此格式）：

[OUTLINE]
{
  "project_name": "项目名称",
  "domain": "所属领域",
  "target_users": ["用户类型1", "用户类型2"],
  "business_model": "业务模式描述",
  "core_modules": [
    {"name": "模块名称", "description": "模块简述"}
  ],
  "feature_list": [
    "模块名称 - 功能点1",
    "模块名称 - 功能点2"
  ],
  "tech_requirements": ["技术要求1", "技术要求2"],
  "complexity": "简单/中等/复杂"
}
[/OUTLINE]

注意事项：
- [OUTLINE] 和 [/OUTLINE] 必须各占一行
- JSON 内容必须是合法的 JSON 格式
- feature_list 中的每一项格式为 "模块名称 - 功能点描述"
- 不要过早输出大纲，至少经过 2 轮有实质内容的对话再考虑输出
- 如果用户主动表示"可以了"或"差不多了"，可以提前输出大纲

## 导出指令识别

当用户要求"导出"、"生成附件"、"转为Word/PDF/PPT"、"下载文档"等操作时，你需要：

1. 判断用户要导出的内容类型（content_type）：
   - 如果用户要求生成"需求大纲"文档，content_type 为 "outline"
   - 如果用户要求生成"需求详细设计"文档，content_type 为 "detail"
   - 如果用户要求生成"立项报告"文档，content_type 为 "proposal_ppt"
   - 如果是其他内容（比如"把上面的讨论整理成Word"、"帮我把这段内容导出为PDF"），content_type 为 "chat"

2. 判断导出格式（format），只能是以下之一：docx、pdf、pptx
   - 用户说"Word"对应 "docx"
   - 用户说"PDF"对应 "pdf"
   - 用户说"PPT"或"演示文稿"对应 "pptx"
   - 如果用户没有指定格式，立项报告默认 "pptx"，其他默认 "docx"

3. 正常回复用户（如"好的，我来帮你生成Word文档..."），然后在回复末尾附加标记：

[EXPORT]
{"format": "docx", "content_type": "chat"}
[/EXPORT]

注意：
- [EXPORT] 和 [/EXPORT] 必须各占一行
- JSON 内容必须是合法的 JSON 格式
- [EXPORT] 标记和 [OUTLINE] 标记不能同时出现在同一条回复中
- 只有当用户明确表达导出/生成文件意图时才使用此标记
"""

# ── 大纲检测正则 ──────────────────────────────────────────────────

_OUTLINE_PATTERN = re.compile(
    r"\[OUTLINE\]\s*\n(.*?)\n\s*\[/OUTLINE\]",
    re.DOTALL,
)

# ── 导出指令检测正则 ──────────────────────────────────────────────

_EXPORT_PATTERN = re.compile(
    r"\[EXPORT\]\s*\n(.*?)\n\s*\[/EXPORT\]",
    re.DOTALL,
)


@dataclass
class OutlineData:
    """从 LLM 回复中解析出的需求大纲结构。"""
    project_name: str = ""
    domain: str = ""
    target_users: list[str] = field(default_factory=list)
    business_model: str = ""
    core_modules: list[dict] = field(default_factory=list)
    feature_list: list[str] = field(default_factory=list)
    tech_requirements: list[str] = field(default_factory=list)
    complexity: str = "中等"

    def to_dict(self) -> dict:
        """转为字典，方便 JSON 序列化。"""
        return {
            "project_name": self.project_name,
            "domain": self.domain,
            "target_users": self.target_users,
            "business_model": self.business_model,
            "core_modules": self.core_modules,
            "feature_list": self.feature_list,
            "tech_requirements": self.tech_requirements,
            "complexity": self.complexity,
        }


def parse_outline(text: str) -> tuple[str, Optional[OutlineData]]:
    """
    从 LLM 回复文本中检测并提取 [OUTLINE] 标记。

    Returns:
        (clean_text, outline): clean_text 是去除标记后的纯文本，
        outline 在未检测到标记时为 None。
    """
    match = _OUTLINE_PATTERN.search(text)
    if not match:
        return text, None

    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()

    try:
        data = json.loads(json_str)
        outline = OutlineData(
            project_name=data.get("project_name", ""),
            domain=data.get("domain", ""),
            target_users=data.get("target_users", []),
            business_model=data.get("business_model", ""),
            core_modules=data.get("core_modules", []),
            feature_list=data.get("feature_list", []),
            tech_requirements=data.get("tech_requirements", []),
            complexity=data.get("complexity", "中等"),
        )
        logger.info("检测到需求大纲: project=%s, features=%d",
                     outline.project_name, len(outline.feature_list))
        return clean_text, outline
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("大纲 JSON 解析失败: %s", exc)
        return text, None


def detect_export_intent_from_user(user_input: str) -> Optional[dict]:
    """
    通过关键词匹配检测用户输入是否包含导出意图（兜底方案）。
    当 LLM 未输出 [EXPORT] 标记时，由此函数在后端直接识别用户的导出需求。

    Args:
        user_input: 用户原始输入文本

    Returns:
        检测到导出意图时返回 {"format": "...", "content_type": "..."}，
        否则返回 None
    """
    text = user_input.strip().lower()

    # 判断是否包含导出/生成附件相关关键词
    export_keywords = [
        "导出", "生成word", "生成pdf", "生成ppt", "转为word", "转为pdf", "转为ppt",
        "转成word", "转成pdf", "转成ppt", "下载word", "下载pdf", "下载ppt",
        "生成文档", "导出文档", "生成附件", "导出附件",
        "word文档", "pdf文档", "ppt文档", "pptx", "docx",
        "帮我生成一份", "输出为word", "输出为pdf", "输出为ppt",
        "输出word", "输出pdf", "输出ppt",
    ]

    has_export_intent = any(kw in text for kw in export_keywords)
    if not has_export_intent:
        return None

    # 判断导出格式
    fmt = "docx"
    if any(kw in text for kw in ["pdf"]):
        fmt = "pdf"
    elif any(kw in text for kw in ["ppt", "pptx", "演示文稿", "幻灯片"]):
        fmt = "pptx"

    # 判断内容类型
    content_type = "chat"
    if any(kw in text for kw in ["需求大纲", "大纲文档"]):
        content_type = "outline"
    elif any(kw in text for kw in ["详细设计", "详设", "需求文档", "需求详细"]):
        content_type = "detail"
    elif any(kw in text for kw in ["立项报告", "立项", "proposal"]):
        content_type = "proposal_ppt"
        if fmt == "docx":
            fmt = "pptx"

    logger.info("用户输入关键词检测到导出意图: format=%s, content_type=%s, input='%s'",
                fmt, content_type, user_input[:50])
    return {"format": fmt, "content_type": content_type}


def parse_export_command(text: str) -> tuple[str, Optional[dict]]:
    """
    从 LLM 回复文本中检测并提取 [EXPORT] 标记。

    Returns:
        (clean_text, export_info): clean_text 是去除标记后的纯文本，
        export_info 在未检测到标记时为 None，否则为
        {"format": "docx"|"pdf"|"pptx", "content_type": "chat"|"outline"|"detail"|"proposal_ppt"}
    """
    match = _EXPORT_PATTERN.search(text)
    if not match:
        return text, None

    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()

    try:
        data = json.loads(json_str)
        fmt = data.get("format", "docx")
        content_type = data.get("content_type", "chat")
        # 校验合法值
        if fmt not in ("docx", "pdf", "pptx"):
            fmt = "docx"
        if content_type not in ("chat", "outline", "detail", "proposal_ppt"):
            content_type = "chat"
        export_info = {"format": fmt, "content_type": content_type}
        logger.info("检测到导出指令: format=%s, content_type=%s", fmt, content_type)
        return clean_text, export_info
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("导出指令 JSON 解析失败: %s", exc)
        return text, None


# ── 会话管理 ──────────────────────────────────────────────────────

def create_session(title: str = "") -> dict:
    """创建一个新的对话会话。"""
    session_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, status, created_at, updated_at) "
            "VALUES (?, ?, 'active', ?, ?)",
            (session_id, title, now, now),
        )
    logger.info("创建会话: %s", session_id)
    return {"id": session_id, "title": title, "status": "active", "created_at": now}


def get_session(session_id: str) -> Optional[dict]:
    """获取会话基本信息。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        return None
    return dict(row)


def list_sessions() -> list[dict]:
    """列出所有会话，按创建时间倒序。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(session_id: str) -> bool:
    """删除会话及其所有消息。"""
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        deleted = conn.execute(
            "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
        ).rowcount
    return deleted > 0


def update_session(session_id: str, **kwargs) -> None:
    """更新会话字段（title, status, outline, task_id 等）。"""
    allowed = {"title", "status", "outline", "task_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE chat_sessions SET {set_clause} WHERE id = ?", values
        )


# ── 消息管理 ──────────────────────────────────────────────────────

def save_message(
    session_id: str,
    role: str,
    content: str,
    msg_type: str = "text",
    metadata: dict | None = None,
) -> str:
    """
    将一条消息持久化到数据库。

    Args:
        session_id: 会话 ID
        role: user / assistant / system
        content: 消息文本
        msg_type: text / outline / progress / artifact
        metadata: 附加的结构化数据（JSON）
    Returns:
        消息 ID
    """
    msg_id = uuid.uuid4().hex[:16]
    now = datetime.datetime.now().isoformat()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_messages "
            "(id, session_id, role, content, msg_type, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, msg_type, meta_json, now),
        )
    # 用第一条用户消息的前 30 字作为会话标题
    if role == "user":
        session = get_session(session_id)
        if session and not session.get("title"):
            title = content[:30].replace("\n", " ")
            update_session(session_id, title=title)
    return msg_id


def get_messages(session_id: str) -> list[dict]:
    """获取某会话的所有消息，按时间正序。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        result.append(d)
    return result


# ── 对话引擎核心 ──────────────────────────────────────────────────

def build_llm_messages(session_id: str) -> list[dict]:
    """
    构建发给 LLM 的 messages 数组。
    包含 system prompt + 会话中所有 user/assistant 消息。
    """
    messages_db = get_messages(session_id)
    llm_messages = [{"role": "system", "content": CONVERSATION_SYSTEM_PROMPT}]
    for m in messages_db:
        if m["role"] in ("user", "assistant"):
            llm_messages.append({"role": m["role"], "content": m["content"]})
    return llm_messages


def chat_stream(session_id: str, user_input: str) -> Generator[dict, None, None]:
    """
    处理一轮对话：保存用户消息 → 调用 LLM 流式生成 → 逐 chunk 推送。

    Yields:
        dict 事件对象，类型有：
        - {"type": "text", "content": "..."} — 文本片段
        - {"type": "outline", "data": {...}} — 检测到大纲
        - {"type": "export", "data": {"format": "...", "content_type": "..."}} — 检测到导出指令
        - {"type": "done"} — 结束
    """
    save_message(session_id, "user", user_input)
    llm_messages = build_llm_messages(session_id)

    full_response = ""
    try:
        for chunk in call_chat_stream(llm_messages):
            full_response += chunk
            yield {"type": "text", "content": chunk}
    except Exception as exc:
        logger.exception("LLM 流式调用失败: %s", exc)
        error_msg = f"抱歉，AI 服务暂时不可用：{exc}"
        save_message(session_id, "assistant", error_msg)
        yield {"type": "text", "content": error_msg}
        yield {"type": "done"}
        return

    # 解析完整回复，检测是否包含大纲或导出指令（两者互斥）
    clean_text, outline = parse_outline(full_response)

    if outline:
        save_message(session_id, "assistant", clean_text)
        outline_dict = outline.to_dict()
        save_message(
            session_id, "assistant", "",
            msg_type="outline",
            metadata=outline_dict,
        )
        update_session(
            session_id,
            status="active",
            outline=json.dumps(outline_dict, ensure_ascii=False),
        )
        yield {"type": "outline", "data": outline_dict}
    else:
        # 尝试检测 LLM 输出中的 [EXPORT] 标记
        clean_text_export, export_info = parse_export_command(full_response)
        if export_info:
            save_message(session_id, "assistant", clean_text_export)
            yield {"type": "export", "data": export_info}
        else:
            save_message(session_id, "assistant", full_response)
            # 兜底：LLM 未输出 [EXPORT] 标记时，通过用户输入关键词检测导出意图
            fallback_export = detect_export_intent_from_user(user_input)
            if fallback_export:
                logger.info("LLM 未输出 [EXPORT] 标记，使用关键词兜底检测触发导出")
                yield {"type": "export", "data": fallback_export}

    yield {"type": "done"}


def confirm_outline(session_id: str) -> dict:
    """
    用户确认大纲，将会话状态更新为 confirmed。

    Returns:
        包含 outline 数据的字典，供 Skill Pipeline 使用。
    """
    session = get_session(session_id)
    if not session:
        return {"success": False, "message": "会话不存在"}
    if not session.get("outline"):
        return {"success": False, "message": "尚未生成需求大纲，请继续对话"}

    outline = json.loads(session["outline"])
    update_session(session_id, status="confirmed")
    save_message(
        session_id, "system",
        "用户已确认需求大纲，正在启动文档生成...",
        msg_type="progress",
    )
    logger.info("会话 %s 大纲已确认，准备启动 Skill Pipeline", session_id)
    return {"success": True, "outline": outline, "session_id": session_id}
