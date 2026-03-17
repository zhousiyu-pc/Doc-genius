"""
对话引擎 — LLM 多轮对话式需求分析
================================
通过自然对话理解用户意图，逐步澄清需求，
当信息充分时自动输出结构化的需求大纲。

核心职责：
- 管理对话历史，构建发给 LLM 的 messages 数组
- 解析 LLM 回复中的 [OUTLINE] 标记，提取结构化大纲
- 提供会话的 CRUD 和消息持久化
- 支持双模式：自由对话 (free) 和 敏捷工程 (agile)
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

# ── 阶段定义 ──────────────────────────────────────────────────────

STAGES = [
    {"id": "discovery", "label": "需求洞察", "desc": "理解用户痛点、目标群体、使用场景与市场背景"},
    {"id": "business_case", "label": "立项论证", "desc": "ROI 分析、可行性评估、竞品对标与风险识别"},
    {"id": "product_backlog", "label": "产品规划", "desc": "MVP 范围定义、用户故事编写、优先级排序"},
    {"id": "architecture", "label": "架构设计", "desc": "技术选型、系统架构、数据库 ER、API 契约设计"},
    {"id": "ux_prototype", "label": "交互原型", "desc": "页面流程、交互规范、UI 视觉风格说明"},
    {"id": "delivery_plan", "label": "交付计划", "desc": "迭代拆分、资源估算、测试策略与上线方案"},
    {"id": "review", "label": "评审输出", "desc": "汇总所有阶段成果，生成可交付的完整文档包"},
]

# ── 需求分析师 System Prompt ──────────────────────────────────────

CONVERSATION_SYSTEM_PROMPT = """你是一位资深的技术产品专家，同时具备产品经理、系统架构师与一线工程师的综合视角。
你遵循"以产品结果负责"的原则，支持两种工作模式：

### 模式 1：自由对话模式 (free)
该模式下，你通过自然对话帮助用户零散地记录想法。
- 当你认为信息充分时，输出结构化的需求大纲 [OUTLINE]。
- 用户可以随时跳跃式地讨论任何话题。

### 模式 2：敏捷工程模式 (agile) —— 严格遵循软件工程规范

该模式下，你必须严格遵循敏捷开发的递进流程。当前处于哪个阶段，你就专注于该阶段的深度讨论。
七个阶段依次为：

1. **需求洞察 (discovery)**：
   - 理解用户的原始想法、痛点和使用场景
   - 明确目标用户群体画像、使用频率
   - 梳理市场背景和行业现状
   - 每次只问 1-2 个关键问题，逐步深入
   - 信息充分后输出 [OUTLINE]（结构化大纲）

2. **立项论证 (business_case)**：
   - **投入分析**：预估研发人力、周期、技术成本
   - **产出分析**：预期收益、效率提升、成本节省
   - **ROI 测算**：投资回报比、回本周期
   - **竞品对标**：市场上已有方案的优劣对比
   - **风险评估**：技术风险、市场风险、组织风险
   - **可行性结论**：给出"建议立项"/"需调整"/"不建议"的明确判断

3. **产品规划 (product_backlog)**：
   - 定义 MVP 最小可行产品范围
   - 编写符合 INVEST 原则的用户故事（Epic → Story → 验收标准）
   - 按 MoSCoW 法则排列优先级（Must / Should / Could / Won't）
   - 输出完整的产品 Backlog

4. **架构设计 (architecture)**：
   - 技术栈选型与理由
   - 系统架构图（微服务 / 单体 / 混合）
   - 数据库 ER 模型设计（表结构、字段、关系）
   - 核心 API 接口契约定义
   - 第三方集成方案

5. **交互原型 (ux_prototype)**：
   - 核心页面流程图
   - 关键页面交互说明（操作 → 反馈 → 异常）
   - UI 视觉风格定义（色彩、字体、组件规范）
   - 移动端 / PC 端适配策略

6. **交付计划 (delivery_plan)**：
   - 迭代拆分（Sprint 1 / 2 / 3 … 各自交付什么）
   - 资源估算（前端 / 后端 / 测试各需多少人天）
   - 测试策略（单元测试、集成测试、验收测试）
   - 上线方案（灰度策略、回滚预案、监控指标）

7. **评审输出 (review)**：
   - 汇总各阶段产出的核心成果
   - 生成完整的可交付文档包
   - 标注遗留问题和后续迭代方向

**敏捷模式行为准则（用户主导，不自动切换）：**
- **引导式对话**：主动引导用户完成当前阶段，不要过早跳到下一阶段
- **环节完成询问**：当当前阶段内容充分详尽时，输出 [STAGE_READY] 询问用户，**不要**输出 [STAGE_COMPLETE] 自动切换
- **附件由用户决定**：每个环节结束时，提醒用户"如需生成本环节附件，可点击生成 Word/PDF/PPT"
- **随时回退**：用户可以跳回任何已完成阶段深度完善，你要配合
- **专业补充**：对用户遗漏的关键内容，主动提出建议而非等待

---

## 核心输出标记 (必须严格遵循格式)

### 1. 环节完成询问 [STAGE_READY] (仅敏捷模式)
当当前环节内容已足够、可进入下一环节时，输出：
[STAGE_READY]{"stage": "当前阶段ID", "summary": "本环节成果简要摘要"}[/STAGE_READY]
后面紧跟一句自然语言询问，例如："本环节内容已足够，是否进入下一环节？如需生成本环节附件，可随时操作。"

### 2. 需求大纲 [OUTLINE] (适用于 discovery 阶段)
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

### 3. 敏捷阶段成果 (里程碑)
在每个阶段对话结束或达成重要共识时，请输出：
[MILESTONE]{"stage": "当前阶段ID", "title": "成果标题"}[/MILESTONE]
后面紧跟该阶段的详细设计内容（Markdown）。

---

## 导出指令识别
当用户要求"导出"、"生成附件"、"转为Word/PDF/PPT"、"下载文档"等操作时，你需要回复 [EXPORT] 标记。

## 文件处理能力
用户可能会上传文件让你帮忙分析、补充、完善或优化。完成后主动提示用户导出。

## 通用原则
- 少用技术术语，多用业务语言。
- 所有设计优先支持最小可用产品 (MVP)。
- 默认给用户"最优选择"，不把决策成本转移给用户。
"""

# ── 正则表达式 ──────────────────────────────────────────────────

_OUTLINE_PATTERN = re.compile(
    r"\[OUTLINE\]\s*\n(.*?)\n\s*\[/OUTLINE\]",
    re.DOTALL,
)

_EXPORT_PATTERN = re.compile(
    r"\[EXPORT\]\s*\n(.*?)\n\s*\[/EXPORT\]",
    re.DOTALL,
)

_STAGE_COMPLETE_PATTERN = re.compile(
    r"\[STAGE_COMPLETE\]\s*\n(.*?)\n\s*\[/STAGE_COMPLETE\]",
    re.DOTALL,
)

_STAGE_READY_PATTERN = re.compile(
    r"\[STAGE_READY\]\s*\n(.*?)\n\s*\[/STAGE_READY\]",
    re.DOTALL,
)

_MILESTONE_PATTERN = re.compile(
    r"\[MILESTONE\]\s*\n(.*?)\n\s*\[/MILESTONE\]",
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
    """从回复中提取 [OUTLINE]"""
    match = _OUTLINE_PATTERN.search(text)
    if not match:
        return text, None
    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()
    try:
        data = json.loads(json_str)
        outline = OutlineData(**{k: v for k, v in data.items() if k in OutlineData.__dataclass_fields__})
        return clean_text, outline
    except Exception as exc:
        logger.warning("大纲 JSON 解析失败: %s", exc)
        return text, None


def parse_stage_complete(text: str) -> tuple[str, Optional[dict]]:
    """提取 [STAGE_COMPLETE]（已弃用，保留兼容）"""
    match = _STAGE_COMPLETE_PATTERN.search(text)
    if not match:
        return text, None
    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()
    try:
        return clean_text, json.loads(json_str)
    except:
        return text, None


def parse_stage_ready(text: str) -> tuple[str, Optional[dict]]:
    """提取 [STAGE_READY]：AI 询问用户是否进入下一环节"""
    match = _STAGE_READY_PATTERN.search(text)
    if not match:
        return text, None
    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()
    try:
        return clean_text, json.loads(json_str)
    except:
        return text, None


def detect_stage_advance_intent(user_input: str) -> bool:
    """检测用户是否明确表示要进入下一环节"""
    text = user_input.strip()
    keywords = ["进入下一环节", "进入下一阶段", "可以了，进入下一环节", "下一环节", "确认进入下一环节"]
    return any(kw in text for kw in keywords)


def parse_milestone(text: str) -> tuple[str, Optional[dict]]:
    """提取 [MILESTONE]"""
    match = _MILESTONE_PATTERN.search(text)
    if not match:
        return text, None
    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()
    try:
        return clean_text, json.loads(json_str)
    except:
        return text, None


def detect_export_intent_from_user(user_input: str) -> Optional[dict]:
    """通过关键词检测导出意图"""
    text = user_input.strip().lower()
    export_keywords = ["导出", "生成word", "生成pdf", "生成ppt", "下载文档", "生成附件"]
    if not any(kw in text for kw in export_keywords):
        return None
    fmt = "pdf" if "pdf" in text else ("pptx" if "ppt" in text else "docx")
    content_type = "chat"
    if "大纲" in text: content_type = "outline"
    elif "详细" in text: content_type = "detail"
    elif "立项" in text: content_type = "proposal_ppt"
    return {"format": fmt, "content_type": content_type}


def parse_export_command(text: str) -> tuple[str, Optional[dict]]:
    """从回复中提取 [EXPORT]"""
    match = _EXPORT_PATTERN.search(text)
    if not match:
        return text, None
    json_str = match.group(1).strip()
    clean_text = text[:match.start()].rstrip()
    try:
        return clean_text, json.loads(json_str)
    except:
        return text, None


# ── 会话管理 ──────────────────────────────────────────────────────

def create_session(title: str = "", mode: str = "free", user_id: str = "", model: str = None) -> dict:
    """
    创建新的对话会话。

    Args:
        title: 会话标题（可选，为空时由第一条消息自动设置）
        mode: 对话模式 - 'free'(自由对话) 或 'agile'(敏捷工程)
        user_id: 用户 ID（认证模式下必填）
        model: 模型 ID（可选，None 则使用默认模型）
    Returns:
        会话字典，包含 id/title/status/mode/current_stage/model/created_at
    """
    session_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.now().isoformat()
    initial_stage = "discovery" if mode == "agile" else ""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, status, mode, current_stage, user_id, model, created_at, updated_at) "
            "VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)",
            (session_id, title, mode, initial_stage, user_id, model, now, now),
        )
    return {"id": session_id, "title": title, "status": "active", "mode": mode, "current_stage": initial_stage, "model": model, "created_at": now}


def get_session(session_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def list_sessions(user_id: str = "") -> list[dict]:
    with get_db() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def search_sessions(query: str, limit: int = 20, user_id: str = "") -> list[dict]:
    """
    搜索会话：按标题和消息内容模糊匹配。
    user_id 非空时仅搜索该用户的会话。
    """
    like = f"%{query}%"
    with get_db() as conn:
        if user_id:
            title_rows = conn.execute(
                "SELECT * FROM chat_sessions WHERE title LIKE ? AND user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (like, user_id, limit),
            ).fetchall()
        else:
            title_rows = conn.execute(
                "SELECT * FROM chat_sessions WHERE title LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (like, limit),
            ).fetchall()

        msg_rows = conn.execute(
            "SELECT DISTINCT session_id FROM chat_messages WHERE content LIKE ? LIMIT ?",
            (like, limit * 2),
        ).fetchall()
        msg_sids = {r["session_id"] for r in msg_rows}

        seen = set()
        results = []
        for r in title_rows:
            d = dict(r)
            seen.add(d["id"])
            results.append(d)
        if msg_sids - seen:
            placeholders = ",".join("?" for _ in (msg_sids - seen))
            params = list(msg_sids - seen)
            if user_id:
                extra = conn.execute(
                    f"SELECT * FROM chat_sessions WHERE id IN ({placeholders}) AND user_id = ? ORDER BY updated_at DESC",
                    params + [user_id],
                ).fetchall()
            else:
                extra = conn.execute(
                    f"SELECT * FROM chat_sessions WHERE id IN ({placeholders}) ORDER BY updated_at DESC",
                    params,
                ).fetchall()
            results.extend(dict(r) for r in extra)

    return results[:limit]


def delete_session(session_id: str) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        deleted = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,)).rowcount
    return deleted > 0


def update_session(session_id: str, **kwargs) -> None:
    allowed = {"title", "status", "outline", "task_id", "mode", "current_stage"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates: return
    updates["updated_at"] = datetime.datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id]
    with get_db() as conn:
        conn.execute(f"UPDATE chat_sessions SET {set_clause} WHERE id = ?", values)


def save_message(session_id: str, role: str, content: str, msg_type: str = "text", metadata: dict | None = None) -> str:
    msg_id = uuid.uuid4().hex[:16]
    now = datetime.datetime.now().isoformat()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, msg_type, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, msg_type, meta_json, now),
        )
    if role == "user":
        session = get_session(session_id)
        if session and not session.get("title"):
            update_session(session_id, title=content[:30].replace("\n", " "))
    return msg_id


def get_messages(session_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata"]) if d.get("metadata") else {}
        result.append(d)
    return result


def get_stage_summaries(session_id: str) -> list[dict]:
    """
    获取敏捷模式下各环节的成果摘要（用于环节大纲面板展示）。
    从 milestone 消息中按 stage 分组，每个 stage 取最新一条。
    """
    messages = get_messages(session_id)
    by_stage: dict[str, dict] = {}
    for m in messages:
        if m.get("msg_type") != "milestone":
            continue
        meta = m.get("metadata") or {}
        stage_id = meta.get("stage")
        if not stage_id:
            continue
        stage_info = next((s for s in STAGES if s["id"] == stage_id), None)
        by_stage[stage_id] = {
            "stage": stage_id,
            "label": stage_info["label"] if stage_info else stage_id,
            "title": meta.get("title", "阶段性成果"),
            "content": m.get("content", ""),
            "msg_id": m.get("id"),
            "created_at": m.get("created_at", ""),
        }
    # 按 STAGES 顺序返回
    result = []
    for s in STAGES:
        if s["id"] in by_stage:
            result.append(by_stage[s["id"]])
    return result


def advance_stage(session_id: str) -> dict | None:
    """
    用户确认进入下一环节：保存当前环节内容为 milestone，并切换到下一阶段。
    仅在敏捷模式下有效。
    """
    session = get_session(session_id)
    if not session or session.get("mode") != "agile":
        return None
    current = session.get("current_stage", "discovery")
    stage_idx = next((i for i, s in enumerate(STAGES) if s["id"] == current), -1)
    if stage_idx < 0 or stage_idx >= len(STAGES) - 1:
        return None

    messages = get_messages(session_id)
    # 找当前阶段最后一个 milestone，若无则用最后一条 assistant 文本
    last_milestone_for_stage = None
    last_assistant_text = None
    for m in reversed(messages):
        if m.get("msg_type") == "milestone":
            if (m.get("metadata") or {}).get("stage") == current:
                last_milestone_for_stage = m
                break
        if m.get("role") == "assistant" and m.get("msg_type") == "text" and m.get("content"):
            last_assistant_text = m
            break

    if not last_milestone_for_stage and last_assistant_text:
        stage_info = next((s for s in STAGES if s["id"] == current), STAGES[0])
        save_message(
            session_id,
            "assistant",
            last_assistant_text["content"],
            msg_type="milestone",
            metadata={"stage": current, "title": f"{stage_info['label']}成果"},
        )

    next_stage = STAGES[stage_idx + 1]["id"]
    update_session(session_id, current_stage=next_stage)
    return {"current_stage": current, "next_stage": next_stage}


def build_llm_messages(session_id: str) -> list[dict]:
    session = get_session(session_id)
    mode = session.get("mode", "free") if session else "free"
    stage = session.get("current_stage", "discovery") if session else "discovery"
    
    # 构建当前上下文描述
    stage_info = next((s for s in STAGES if s["id"] == stage), STAGES[0])
    mode_prompt = f"\n\n当前模式: {mode}\n当前阶段: {stage_info['label']} ({stage})\n阶段任务: {stage_info['desc']}"
    
    messages_db = get_messages(session_id)
    llm_messages = [{"role": "system", "content": CONVERSATION_SYSTEM_PROMPT + mode_prompt}]
    
    for m in messages_db:
        if m["role"] in ("user", "assistant"):
            if m.get("msg_type") == "file":
                meta = m.get("metadata", {})
                content = f"[用户上传了文件: {meta.get('filename')}]\n{m['content']}"
                llm_messages.append({"role": "user", "content": content})
            else:
                llm_messages.append({"role": m["role"], "content": m["content"]})
    return llm_messages


def chat_stream(session_id: str, user_input: str) -> Generator[dict, None, None]:
    session = get_session(session_id)
    # 敏捷模式：用户说"进入下一环节"时，直接执行切换，不调用 LLM
    if session and session.get("mode") == "agile" and detect_stage_advance_intent(user_input):
        save_message(session_id, "user", user_input)
        result = advance_stage(session_id)
        if result:
            save_message(session_id, "system", f"已进入下一环节：{result['next_stage']}", msg_type="text")
            yield {"type": "stage_advance", "data": result}
        yield {"type": "done"}
        return

    save_message(session_id, "user", user_input)
    llm_messages = build_llm_messages(session_id)
    
    full_response = ""
    try:
        # 获取会话使用的模型（如果有）
        session_model = session.get("model") if session else None
        for chunk in call_chat_stream(llm_messages, model=session_model):
            full_response += chunk
            yield {"type": "text", "content": chunk}
    except Exception as exc:
        logger.exception("LLM 调用失败: %s", exc)
        yield {"type": "text", "content": f"服务异常: {exc}"}
        yield {"type": "done"}
        return

    # 解析标记
    clean_text = full_response
    
    # 1. 环节完成询问 [STAGE_READY]（不自动切换，由用户确认）
    clean_text, stage_ready = parse_stage_ready(clean_text)
    if stage_ready:
        yield {"type": "stage_ready", "data": stage_ready}

    # 2. 里程碑成果
    clean_text, milestone = parse_milestone(clean_text)
    if milestone:
        save_message(session_id, "assistant", clean_text, msg_type="milestone", metadata=milestone)
        yield {"type": "milestone", "data": {**milestone, "content": clean_text}}
    
    # 3. 需求大纲
    clean_text, outline = parse_outline(clean_text)
    if outline:
        outline_dict = outline.to_dict()
        save_message(session_id, "assistant", clean_text)
        save_message(session_id, "assistant", "", msg_type="outline", metadata=outline_dict)
        update_session(session_id, outline=json.dumps(outline_dict, ensure_ascii=False))
        yield {"type": "outline", "data": outline_dict}
    else:
        # 4. 导出
        clean_text, export_info = parse_export_command(clean_text)
        if export_info:
            save_message(session_id, "assistant", clean_text)
            yield {"type": "export", "data": export_info}
        else:
            save_message(session_id, "assistant", clean_text)
            fallback = detect_export_intent_from_user(user_input)
            if fallback: yield {"type": "export", "data": fallback}

    yield {"type": "done"}


def confirm_outline(session_id: str) -> dict:
    session = get_session(session_id)
    if not session or not session.get("outline"):
        return {"success": False, "message": "尚未生成大纲"}
    outline = json.loads(session["outline"])
    update_session(session_id, status="confirmed")
    save_message(session_id, "system", "已确认大纲，启动生成...", msg_type="progress")
    return {"success": True, "outline": outline, "session_id": session_id}
