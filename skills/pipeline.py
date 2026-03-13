"""
Skill 流水线 — 根据用户选择的文档类型并行执行对应 Skill
=====================================================
支持三种文档类型：
- outline: 需求大纲（精简，只含背景+模块）
- detail: 需求详细设计（完整5件套：需求文档+流程图+ER图+测试用例+API文档）
- proposal_ppt: 需求立项报告（背景/ROI/架构/功能/推广）

执行完内容 Skill 后，自动导出 PDF / Word / PPT 文件。
"""

import os
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from core.conversation import save_message, update_session
from skills.base import BaseSkill, SkillResult

logger = logging.getLogger("agent_skills.pipeline")

_pipeline_executor: Optional[ThreadPoolExecutor] = None
_MAX_PIPELINE_WORKERS = 3

# 文档类型 → 对应的 Skill 集合（顺序决定导出文档中的排列顺序）
# detail 中：需求文档 → 接口设计 → 测试用例 → 流程图/ER图（末尾，Mermaid 导出时转 PNG 作附件）
DOC_TYPE_MAP: dict[str, list[str]] = {
    "outline": ["outline_doc"],
    "detail": ["req_doc", "api_doc", "test_cases", "flow_diagram", "er_diagram"],
    "proposal_ppt": ["proposal_ppt"],
}


def init_pipeline_executor() -> None:
    """初始化 Skill 流水线的线程池。"""
    global _pipeline_executor
    if _pipeline_executor is None:
        _pipeline_executor = ThreadPoolExecutor(
            max_workers=_MAX_PIPELINE_WORKERS,
            thread_name_prefix="skill-pipeline",
        )
        logger.info("Skill Pipeline 线程池已启动 (workers=%d)", _MAX_PIPELINE_WORKERS)


def shutdown_pipeline_executor() -> None:
    """关闭线程池。"""
    global _pipeline_executor
    if _pipeline_executor:
        _pipeline_executor.shutdown(wait=False)
        _pipeline_executor = None
        logger.info("Skill Pipeline 线程池已关闭")


def _get_skill_registry() -> dict[str, BaseSkill]:
    """获取所有已注册 Skill 的名称→实例映射。延迟导入避免循环依赖。"""
    from skills.req_doc.skill import RequirementDocSkill
    from skills.flow_diagram.skill import FlowDiagramSkill
    from skills.er_diagram.skill import ERDiagramSkill
    from skills.test_cases.skill import TestCasesSkill
    from skills.api_doc.skill import APIDocSkill
    from skills.outline_doc.skill import OutlineDocSkill
    from skills.proposal_ppt.skill import ProposalReportSkill

    all_skills = [
        RequirementDocSkill(),
        FlowDiagramSkill(),
        ERDiagramSkill(),
        TestCasesSkill(),
        APIDocSkill(),
        OutlineDocSkill(),
        ProposalReportSkill(),
    ]
    return {s.name: s for s in all_skills}


def _resolve_skills(doc_types: list[str]) -> list[BaseSkill]:
    """根据用户选择的文档类型，解析出需要执行的 Skill 列表（去重）。"""
    registry = _get_skill_registry()
    seen = set()
    skills = []
    for dt in doc_types:
        for skill_name in DOC_TYPE_MAP.get(dt, []):
            if skill_name not in seen:
                seen.add(skill_name)
                skill = registry.get(skill_name)
                if skill:
                    skills.append(skill)
    return skills


def _default_export_formats(doc_types: list[str]) -> list[str]:
    """根据文档类型推导默认的导出格式（立项报告→PPT，其他→Word）。"""
    _type_fmt_map = {
        "outline": ["docx"],
        "detail": ["docx"],
        "proposal_ppt": ["pptx"],
    }
    formats = set()
    for dt in (doc_types or ["detail"]):
        for fmt in _type_fmt_map.get(dt, ["docx"]):
            formats.add(fmt)
    return list(formats) if formats else ["docx"]


def run_pipeline(
    session_id: str,
    outline: dict,
    doc_configs: dict | None = None,
) -> list[SkillResult]:
    """
    同步执行 Skill 流水线。

    Args:
        session_id: 对话会话 ID
        outline: 确认后的需求大纲
        doc_configs: 包含各个文档类型及其对应的导出格式列表的字典。
                     示例：{"outline": ["docx"], "detail": ["pdf", "docx"], "proposal_ppt": ["pptx"]}
    Returns:
        所有 Skill 的执行结果列表
    """
    global _pipeline_executor
    if _pipeline_executor is None:
        init_pipeline_executor()

    if not doc_configs:
        doc_configs = {"detail": ["docx"]}

    doc_types = list(doc_configs.keys())
    skills = _resolve_skills(doc_types)
    if not skills:
        logger.warning("未找到对应的 Skill: doc_types=%s", doc_types)
        return []

    results: list[SkillResult] = []
    type_labels = {
        "outline": "需求大纲",
        "detail": "需求详细设计",
        "proposal_ppt": "需求立项报告",
    }
    selected_labels = "、".join(type_labels.get(t, t) for t in doc_types)

    update_session(session_id, status="generating")
    save_message(
        session_id, "system",
        f"正在生成 [{selected_labels}]，共 {len(skills)} 项产出物...",
        msg_type="progress",
        metadata={"total": len(skills), "completed": 0, "doc_types": doc_types},
    )

    futures = {}
    for skill in skills:
        future = _pipeline_executor.submit(skill.execute, outline)
        futures[future] = skill

    completed_count = 0
    for future in as_completed(futures):
        skill = futures[future]
        try:
            result = future.result(timeout=300)
        except Exception as exc:
            logger.exception("Skill [%s] 执行超时或异常: %s", skill.name, exc)
            result = SkillResult(
                skill_name=skill.name,
                display_name=skill.display_name,
                output_type=skill.output_type,
                content="",
                title=skill.display_name,
                success=False,
                error=str(exc),
            )

        results.append(result)
        completed_count += 1

        if result.success:
            save_message(
                session_id, "assistant", result.content,
                msg_type="artifact",
                metadata={
                    "skill_name": result.skill_name,
                    "display_name": result.display_name,
                    "output_type": result.output_type,
                    "title": result.title,
                },
            )
            logger.info(
                "Skill [%s] 产出物已保存 (%d/%d)",
                skill.name, completed_count, len(skills),
            )
        else:
            save_message(
                session_id, "system",
                f"{skill.display_name} 生成失败: {result.error}",
                msg_type="progress",
                metadata={"skill_name": result.skill_name, "error": True},
            )

    # 第二阶段：按文档类型分组并分别导出 PDF / Word / PPT
    success_count = sum(1 for r in results if r.success)
    project_name = (outline.get("project_name") or "document").strip() or "document"

    if doc_configs:
        for dt, export_formats in doc_configs.items():
            if not export_formats:
                continue
                
            dt_label = type_labels.get(dt, dt)
            dt_skill_names = DOC_TYPE_MAP.get(dt, [])
            
            # 筛选出属于当前类型的成功产出物，并按 DOC_TYPE_MAP 中的顺序排列
            skill_order = {name: i for i, name in enumerate(dt_skill_names)}
            dt_results = sorted(
                [r for r in results if r.success and r.content and r.skill_name in dt_skill_names],
                key=lambda r: skill_order.get(r.skill_name, 999),
            )
            dt_contents = [(r.display_name, r.content) for r in dt_results]
            
            if dt_contents:
                fmt_labels = {"pdf": "PDF", "docx": "Word", "pptx": "PPT"}
                fmt_desc = "、".join(fmt_labels.get(f, f) for f in export_formats)
                save_message(
                    session_id, "system",
                    f"正在导出 {dt_label} ({fmt_desc})...",
                    msg_type="progress",
                    metadata={"exporting": True},
                )
                
                # 为该文档类型指定特定的文件名后缀，如 "_需求大纲"
                filename_suffix = f"_{dt_label}"
                _run_export_skills(session_id, project_name, dt_contents, export_formats, filename_suffix)

    update_session(session_id, status="completed")
    save_message(
        session_id, "system",
        f"文档生成完成！成功 {success_count}/{len(skills)} 项。",
        msg_type="progress",
        metadata={"total": len(skills), "completed": success_count, "done": True},
    )
    logger.info(
        "会话 %s Pipeline 完毕: %d/%d 成功, doc_types=%s",
        session_id, success_count, len(skills), doc_types,
    )
    return results


def _run_export_skills(
    session_id: str,
    project_name: str,
    contents: list,
    export_formats: list[str] | None = None,
    filename_suffix: str = "_需求与详设",
) -> None:
    """
    按用户选择的导出格式执行导出，将结果写入 artifact 消息。
    每个导出模块独立导入，单个模块失败不影响其他模块。

    Args:
        export_formats: 用户选中的导出格式列表，如 ["pdf", "docx"]。
                        为 None 时默认导出 pdf + docx。
    """
    if export_formats is None:
        export_formats = ["docx"]

    all_export_configs = [
        ("pdf", "PDF 文档", "skills.export_pdf.skill", "export_to_pdf"),
        ("docx", "Word 文档", "skills.export_docx.skill", "export_to_docx"),
        ("pptx", "PPT 演示文稿", "skills.export_pptx.skill", "export_to_pptx"),
    ]
    export_configs = [c for c in all_export_configs if c[0] in export_formats]
    if not export_configs:
        return

    for fmt, display_name, module_path, func_name in export_configs:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            export_fn = getattr(mod, func_name)
        except Exception as imp_exc:
            logger.exception("导出模块 %s 导入失败: %s", module_path, imp_exc)
            save_message(
                session_id, "system",
                f"{display_name} 导出不可用（缺少依赖）: {imp_exc}",
                msg_type="progress",
                metadata={"skill_name": f"export_{fmt}", "error": True},
            )
            continue

        try:
            ok, file_path, err = export_fn(session_id, project_name, contents, filename_suffix)
            if ok and file_path:
                filename = os.path.basename(file_path)
                save_message(
                    session_id, "assistant", "",
                    msg_type="artifact",
                    metadata={
                        "skill_name": f"export_{fmt}",
                        "display_name": display_name,
                        "output_type": fmt,
                        "title": display_name,
                        "export_format": fmt,
                        "filename": filename,
                    },
                )
                logger.info("导出 %s 成功: %s", fmt, filename)
            else:
                save_message(
                    session_id, "system",
                    f"{display_name} 生成失败: {err}",
                    msg_type="progress",
                    metadata={"skill_name": f"export_{fmt}", "error": True},
                )
        except Exception as exc:
            logger.exception("导出 %s 执行异常: %s", fmt, exc)
            save_message(
                session_id, "system",
                f"{display_name} 生成失败: {exc}",
                msg_type="progress",
                metadata={"skill_name": f"export_{fmt}", "error": True},
            )


def run_adhoc_export(
    session_id: str,
    export_format: str,
    content_type: str,
) -> None:
    """
    即时导出：根据用户在对话中的指令，将聊天内容或标准文档导出为指定格式。

    对于标准文档类型（outline/detail/proposal_ppt），需要已确认的大纲，
    走完整的 Skill 流水线生成内容后再导出。

    对于 "chat" 类型，直接收集最近的 assistant 消息内容作为导出素材。

    Args:
        session_id: 会话 ID
        export_format: 导出格式 (docx / pdf / pptx)
        content_type: 内容类型 (chat / outline / detail / proposal_ppt)
    """
    from core.conversation import get_session, get_messages, save_message, update_session

    session = get_session(session_id)
    if not session:
        logger.error("即时导出失败: 会话 %s 不存在", session_id)
        return

    # 标准文档类型：走完整 pipeline
    if content_type in ("outline", "detail", "proposal_ppt"):
        outline_json = session.get("outline")
        if not outline_json:
            save_message(
                session_id, "system",
                "导出失败：尚未生成需求大纲，请先完成需求分析对话。",
                msg_type="progress",
                metadata={"error": True},
            )
            return
        try:
            import json as _json
            outline = _json.loads(outline_json) if isinstance(outline_json, str) else outline_json
        except Exception:
            save_message(
                session_id, "system",
                "导出失败：需求大纲数据异常。",
                msg_type="progress",
                metadata={"error": True},
            )
            return
        doc_configs = {content_type: [export_format]}
        run_pipeline(session_id, outline, doc_configs)
        return

    # chat 类型：收集对话中最近的 assistant 文本消息作为导出内容
    all_messages = get_messages(session_id)
    assistant_texts = []
    for msg in reversed(all_messages):
        if msg["role"] == "assistant" and msg.get("msg_type") == "text" and msg.get("content"):
            assistant_texts.insert(0, msg["content"])
            if len(assistant_texts) >= 5:
                break

    if not assistant_texts:
        save_message(
            session_id, "system",
            "导出失败：对话中没有可导出的内容。",
            msg_type="progress",
            metadata={"error": True},
        )
        return

    project_name = "对话内容"
    if session.get("outline"):
        try:
            import json as _json
            outline_data = _json.loads(session["outline"]) if isinstance(session["outline"], str) else session["outline"]
            project_name = outline_data.get("project_name") or project_name
        except Exception:
            pass

    contents = [("对话内容整理", "\n\n".join(assistant_texts))]

    fmt_labels = {"pdf": "PDF", "docx": "Word", "pptx": "PPT"}
    save_message(
        session_id, "system",
        f"正在将对话内容导出为 {fmt_labels.get(export_format, export_format)} 文档...",
        msg_type="progress",
        metadata={"exporting": True},
    )

    _run_export_skills(
        session_id, project_name, contents,
        export_formats=[export_format],
        filename_suffix="_对话内容",
    )

    save_message(
        session_id, "system",
        "文档导出完成！",
        msg_type="progress",
        metadata={"done": True},
    )


def run_selected_export(
    session_id: str,
    export_format: str,
    message_ids: list[str],
) -> None:
    """
    按用户选择的消息导出：收集指定消息 ID 的内容，导出为指定格式文件。

    Args:
        session_id: 会话 ID
        export_format: 导出格式 (docx / pdf / pptx)
        message_ids: 用户选中的消息 ID 列表
    """
    from core.conversation import get_session, get_messages, save_message

    session = get_session(session_id)
    if not session:
        logger.error("选择导出失败: 会话 %s 不存在", session_id)
        return

    all_messages = get_messages(session_id)
    id_set = set(message_ids)

    # 按原始顺序保留用户选中的消息内容
    selected_texts = []
    for msg in all_messages:
        if msg["id"] in id_set and msg.get("content"):
            selected_texts.append(msg["content"])

    if not selected_texts:
        save_message(
            session_id, "system",
            "导出失败：未找到选中的消息内容。",
            msg_type="progress",
            metadata={"error": True, "done": True},
        )
        return

    project_name = "对话内容"
    if session.get("outline"):
        try:
            outline_data = json.loads(session["outline"]) if isinstance(session["outline"], str) else session["outline"]
            project_name = outline_data.get("project_name") or project_name
        except Exception:
            pass

    contents = [("对话内容整理", "\n\n---\n\n".join(selected_texts))]

    fmt_labels = {"pdf": "PDF", "docx": "Word", "pptx": "PPT"}
    save_message(
        session_id, "system",
        f"正在将选中的 {len(selected_texts)} 条消息导出为 {fmt_labels.get(export_format, export_format)} 文档...",
        msg_type="progress",
        metadata={"exporting": True},
    )

    _run_export_skills(
        session_id, project_name, contents,
        export_formats=[export_format],
        filename_suffix="_对话内容",
    )

    save_message(
        session_id, "system",
        "文档导出完成！",
        msg_type="progress",
        metadata={"done": True},
    )


async def run_selected_export_async(
    session_id: str,
    export_format: str,
    message_ids: list[str],
) -> None:
    """异步包装：在线程池中运行选择导出。"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, run_selected_export, session_id, export_format, message_ids
    )


async def run_adhoc_export_async(
    session_id: str,
    export_format: str,
    content_type: str,
) -> None:
    """异步包装：在线程池中运行即时导出。"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, run_adhoc_export, session_id, export_format, content_type
    )


async def run_pipeline_async(
    session_id: str,
    outline: dict,
    doc_configs: dict | None = None,
) -> list[SkillResult]:
    """异步包装：在线程池中运行同步的 Skill 流水线。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, run_pipeline, session_id, outline, doc_configs
    )
