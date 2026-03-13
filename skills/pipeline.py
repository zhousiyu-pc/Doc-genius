"""
Skill 流水线 — 并行执行多个 Skill 生成产出物
=============================================
接收确认后的需求大纲，并行调用所有注册的 Skill，
将每个 Skill 的结果作为 artifact 消息写入对话会话。
"""

import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from core.conversation import save_message, update_session, get_session
from skills.base import BaseSkill, SkillResult

logger = logging.getLogger("agent_skills.pipeline")

_pipeline_executor: Optional[ThreadPoolExecutor] = None
_MAX_PIPELINE_WORKERS = 3


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


def get_all_skills() -> list[BaseSkill]:
    """
    获取所有已注册的 Skill 实例。
    延迟导入以避免循环依赖。
    """
    from skills.req_doc.skill import RequirementDocSkill
    from skills.flow_diagram.skill import FlowDiagramSkill
    from skills.er_diagram.skill import ERDiagramSkill
    from skills.test_cases.skill import TestCasesSkill
    from skills.api_doc.skill import APIDocSkill

    return [
        RequirementDocSkill(),
        FlowDiagramSkill(),
        ERDiagramSkill(),
        TestCasesSkill(),
        APIDocSkill(),
    ]


def run_pipeline(session_id: str, outline: dict) -> list[SkillResult]:
    """
    同步执行 Skill 流水线：并行调用所有 Skill，收集结果。

    每个 Skill 完成后，将结果作为 artifact 类型消息保存到会话中，
    前端通过轮询会话消息即可获取产出物。

    Args:
        session_id: 对话会话 ID
        outline: 确认后的需求大纲
    Returns:
        所有 Skill 的执行结果列表
    """
    global _pipeline_executor
    if _pipeline_executor is None:
        init_pipeline_executor()

    skills = get_all_skills()
    results: list[SkillResult] = []

    update_session(session_id, status="generating")
    save_message(
        session_id, "system",
        f"正在并行生成 {len(skills)} 项产出物，请稍候...",
        msg_type="progress",
        metadata={"total": len(skills), "completed": 0},
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
                "Skill [%s] 产出物已保存到会话 (%d/%d)",
                skill.name, completed_count, len(skills),
            )
        else:
            save_message(
                session_id, "system",
                f"{skill.display_name} 生成失败: {result.error}",
                msg_type="progress",
                metadata={
                    "skill_name": result.skill_name,
                    "error": True,
                },
            )

    # 全部完成，更新会话状态
    success_count = sum(1 for r in results if r.success)
    update_session(session_id, status="completed")
    save_message(
        session_id, "system",
        f"文档生成完成！成功 {success_count}/{len(skills)} 项。",
        msg_type="progress",
        metadata={"total": len(skills), "completed": success_count, "done": True},
    )
    logger.info(
        "会话 %s 的 Skill Pipeline 执行完毕: %d/%d 成功",
        session_id, success_count, len(skills),
    )
    return results


async def run_pipeline_async(session_id: str, outline: dict) -> list[SkillResult]:
    """
    异步包装：在线程池中运行同步的 Skill 流水线。
    供 conversation routes 中的 confirm 接口使用。
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_pipeline, session_id, outline)
