"""
任务管理 Skill — 核心业务逻辑
==============================
任务提交、子任务处理（含重试）、任务恢复。
任务完成后自动汇总文档并保存为 Markdown 文件。
"""

import json
import uuid
import time
import sqlite3
import logging
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from ...core.config import (
    TASK_WORKERS, MAX_RETRIES, RETRY_INTERVALS,
    LLM_API_KEY, DB_PATH,
)
from ...core.db import get_db
from ...core.llm_client import call_completion
from ...core.logger import get_task_logger
from ..file_saver.service import save_file

logger = logging.getLogger("agent_skills.task_manager")

_executor: ThreadPoolExecutor | None = None
_shutdown_event = threading.Event()


# ── Markdown 文档汇总模板 ───────────────────────────

_DOC_TEMPLATE = """# {project_name}

## 一、项目概述

{project_summary}

- **业务模式**：{business_model}
- **目标市场**：{target_market}
- **对接平台**：{platforms}

## 二、跨境电商特有考虑

{cross_border_notes}

## 三、系统整体架构图

```mermaid
{architecture_diagram}
```

## 四、系统核心流程图

```mermaid
{flowchart_diagram}
```

## 五、功能模块总览

{module_overview}

## 六、功能点详细设计

{feature_details_text}
"""


def init_executor():
    """初始化线程池"""
    global _executor
    _executor = ThreadPoolExecutor(
        max_workers=TASK_WORKERS,
        thread_name_prefix="task-worker",
    )
    logger.info("线程池已创建，并发 Worker 数: %d", TASK_WORKERS)


def shutdown_executor():
    """关闭线程池"""
    global _executor
    _shutdown_event.set()
    if _executor:
        _executor.shutdown(wait=False)
        logger.info("线程池已关闭")


def _process_sub_task(task_id: str, sub_task_id: str):
    """
    处理单个子任务：调用 LLM API 生成功能点详设。
    包含重试逻辑和状态持久化。
    若子任务已为 completed/failed 则直接跳过，避免重复提交导致的重复计数。
    """
    task_log = get_task_logger(task_id)

    with get_db() as conn:
        row = conn.execute(
            "SELECT feature_name, retry_count, status FROM sub_tasks WHERE id = ?",
            (sub_task_id,),
        ).fetchone()
        if not row:
            task_log.error("子任务不存在: %s", sub_task_id)
            return
        if row["status"] in ("completed", "failed"):
            task_log.debug("子任务已终态，跳过: [%s] status=%s", sub_task_id, row["status"])
            return

        feature_name = row["feature_name"]
        current_retry = row["retry_count"]

        task_row = conn.execute(
            "SELECT context, business_model, target_market, platforms, detail_level "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        conn.execute(
            "UPDATE sub_tasks SET status = 'running', started_at = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), sub_task_id),
        )

    task_log.info("开始处理功能点: [%s] (重试次数: %d)", feature_name, current_retry)

    llm_context = task_row["context"]
    try:
        ctx_obj = json.loads(llm_context)
        if isinstance(ctx_obj, dict) and "_llm_context" in ctx_obj:
            llm_context = ctx_obj["_llm_context"]
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        result_text = call_completion(
            feature_name=feature_name,
            project_context=llm_context,
            business_model=task_row["business_model"],
            target_market=task_row["target_market"],
            platforms=task_row["platforms"],
            detail_level=task_row["detail_level"],
        )

        now = datetime.datetime.now().isoformat()
        with get_db() as conn:
            conn.execute(
                "UPDATE sub_tasks SET status = 'completed', result = ?, finished_at = ? WHERE id = ?",
                (result_text, now, sub_task_id),
            )
            conn.execute(
                "UPDATE tasks SET completed_count = completed_count + 1, updated_at = ? WHERE id = ?",
                (now, task_id),
            )

        task_log.info("功能点完成: [%s] (结果长度: %d 字符)", feature_name, len(result_text))
        _check_task_completion(task_id, task_log)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        task_log.error("功能点失败: [%s] 错误: %s", feature_name, error_msg)

        next_retry = current_retry + 1
        if next_retry < MAX_RETRIES:
            retry_interval = RETRY_INTERVALS[min(next_retry - 1, len(RETRY_INTERVALS) - 1)]
            task_log.info(
                "将在 %d 秒后重试功能点 [%s] (第 %d/%d 次)",
                retry_interval, feature_name, next_retry, MAX_RETRIES,
            )
            with get_db() as conn:
                conn.execute(
                    "UPDATE sub_tasks SET status = 'pending', retry_count = ?, error_message = ? WHERE id = ?",
                    (next_retry, error_msg, sub_task_id),
                )

            if not _shutdown_event.is_set():
                time.sleep(retry_interval)
                if _executor and not _shutdown_event.is_set():
                    _executor.submit(_process_sub_task, task_id, sub_task_id)
        else:
            now = datetime.datetime.now().isoformat()
            with get_db() as conn:
                conn.execute(
                    "UPDATE sub_tasks SET status = 'failed', error_message = ?, finished_at = ? WHERE id = ?",
                    (error_msg, now, sub_task_id),
                )
                conn.execute(
                    "UPDATE tasks SET failed_count = failed_count + 1, updated_at = ? WHERE id = ?",
                    (now, task_id),
                )

            task_log.error(
                "功能点最终失败（已达最大重试次数）: [%s] 错误: %s",
                feature_name, error_msg,
            )
            _check_task_completion(task_id, task_log)


def _check_task_completion(task_id: str, task_log: logging.Logger):
    """
    检查整个任务是否全部完成。
    完成后自动汇总文档并保存为 Markdown 文件。
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT total_count, completed_count, failed_count FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if not row:
            return

        done = row["completed_count"] + row["failed_count"]
        if done >= row["total_count"]:
            now = datetime.datetime.now().isoformat()
            final_status = "completed" if row["failed_count"] == 0 else "partial"
            conn.execute(
                "UPDATE tasks SET status = ?, finished_at = ?, updated_at = ? WHERE id = ?",
                (final_status, now, now, task_id),
            )
            task_log.info(
                "任务完成! 状态: %s, 成功: %d, 失败: %d, 总计: %d",
                final_status, row["completed_count"], row["failed_count"], row["total_count"],
            )

            _auto_assemble_and_save(task_id, task_log)


def _auto_assemble_and_save(task_id: str, task_log: logging.Logger):
    """
    任务完成后自动汇总所有子任务结果，
    套用文档模板生成最终 Markdown，并保存到文件。
    """
    try:
        with get_db() as conn:
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                return

            sub_tasks = conn.execute(
                "SELECT feature_name, status, result FROM sub_tasks "
                "WHERE task_id = ? ORDER BY seq_index",
                (task_id,),
            ).fetchall()

        results = []
        for s in sub_tasks:
            if s["status"] == "completed" and s["result"]:
                results.append(s["result"])
            elif s["status"] == "failed":
                results.append(f"### {s['feature_name']}\n\n> 该功能点生成失败，请稍后重试。\n\n---")

        feature_details_text = "\n\n".join(results)

        doc_context = {}
        try:
            doc_context = json.loads(task["context"]) if task["context"].strip().startswith("{") else {}
        except (json.JSONDecodeError, AttributeError):
            doc_context = {}

        project_name = doc_context.get("project_name", "跨境电商ERP系统")
        save_directory = doc_context.get("save_directory", "")

        markdown = _DOC_TEMPLATE.format(
            project_name=project_name,
            project_summary=doc_context.get("project_summary", ""),
            business_model=task["business_model"] or "B2C零售",
            target_market=task["target_market"] or "全球",
            platforms=task["platforms"] or "未指定",
            cross_border_notes=doc_context.get("cross_border_notes", ""),
            architecture_diagram=doc_context.get("architecture_diagram", ""),
            flowchart_diagram=doc_context.get("flowchart_diagram", ""),
            module_overview=doc_context.get("module_overview", ""),
            feature_details_text=feature_details_text,
        )

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = project_name.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}_{ts}.md"

        save_result = save_file(
            content=markdown,
            filename=filename,
            save_directory=save_directory,
        )

        if save_result.get("success"):
            filepath = save_result["filepath"]
            with get_db() as conn:
                conn.execute(
                    "UPDATE tasks SET result_file = ?, updated_at = ? WHERE id = ?",
                    (filepath, datetime.datetime.now().isoformat(), task_id),
                )
            task_log.info("文档自动保存成功: %s", filepath)
        else:
            task_log.error("文档自动保存失败: %s", save_result.get("message", ""))

    except Exception as e:
        task_log.error("自动汇总保存出错: %s", str(e), exc_info=True)


def submit_task(
    feature_list: list[str],
    context: str,
    business_model: str = "",
    target_market: str = "",
    platforms: str = "",
    detail_level: str = "详细",
    doc_context: dict | None = None,
) -> str:
    """
    提交一个新任务，将功能点列表拆解为子任务并入队执行。

    Args:
        feature_list: 功能点名称列表
        context: 项目背景描述（LLM 用）
        business_model: 业务模式
        target_market: 目标市场
        platforms: 对接平台
        detail_level: 详细程度
        doc_context: 文档汇总上下文（包含 project_name, project_summary,
                     architecture_diagram, flowchart_diagram, module_overview,
                     cross_border_notes, save_directory 等），
                     任务完成后自动汇总并保存文件。

    Returns:
        任务 ID
    """
    task_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.now().isoformat()
    task_log = get_task_logger(task_id)

    stored_context = context
    if doc_context:
        full_ctx = dict(doc_context)
        full_ctx["_llm_context"] = context
        stored_context = json.dumps(full_ctx, ensure_ascii=False)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks (id, feature_list, context, business_model, target_market,
               platforms, detail_level, status, total_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
            (
                task_id,
                json.dumps(feature_list, ensure_ascii=False),
                stored_context,
                business_model,
                target_market,
                platforms,
                detail_level,
                len(feature_list),
                now,
                now,
            ),
        )

        sub_task_ids = []
        for i, feature in enumerate(feature_list):
            sub_id = f"{task_id}_{i:03d}"
            conn.execute(
                """INSERT INTO sub_tasks (id, task_id, feature_name, seq_index, status, created_at)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (sub_id, task_id, feature, i, now),
            )
            sub_task_ids.append(sub_id)

    task_log.info("任务创建成功: task_id=%s, 功能点数量=%d", task_id, len(feature_list))
    for feat in feature_list:
        task_log.info("  - %s", feat)
    if doc_context:
        task_log.info("文档上下文已保存，任务完成后将自动汇总并保存文件")

    if _executor:
        for sub_id in sub_task_ids:
            _executor.submit(_process_sub_task, task_id, sub_id)
        task_log.info("所有子任务已提交到线程池 (并发数: %d)", TASK_WORKERS)

    return task_id


def retry_failed_task(task_id: str) -> dict:
    """
    重试指定任务中所有失败的子任务。
    将 failed 状态的子任务重置为 pending 并重新提交到线程池。

    Returns:
        包含 success, retried_count, message 的字典
    """
    task_log = get_task_logger(task_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return {"success": False, "retried_count": 0, "message": "任务不存在"}

    failed_subs = conn.execute(
        "SELECT id, feature_name FROM sub_tasks WHERE task_id = ? AND status = 'failed'",
        (task_id,),
    ).fetchall()

    if not failed_subs:
        conn.close()
        return {"success": True, "retried_count": 0, "message": "没有失败的子任务需要重试"}

    retried_count = len(failed_subs)
    now = datetime.datetime.now().isoformat()

    conn.execute(
        "UPDATE sub_tasks SET status = 'pending', retry_count = 0, error_message = NULL, "
        "started_at = NULL, finished_at = NULL WHERE task_id = ? AND status = 'failed'",
        (task_id,),
    )
    conn.execute(
        "UPDATE tasks SET status = 'running', failed_count = 0, finished_at = NULL, "
        "result_file = NULL, updated_at = ? WHERE id = ?",
        (now, task_id),
    )
    conn.commit()
    conn.close()

    task_log.info("重试 %d 个失败的子任务", retried_count)

    if _executor:
        for sub in failed_subs:
            _executor.submit(_process_sub_task, task_id, sub["id"])
            task_log.info("重新提交子任务: [%s] %s", sub["id"], sub["feature_name"])

    return {
        "success": True,
        "retried_count": retried_count,
        "message": f"已重新提交 {retried_count} 个失败的子任务",
    }


def sync_task_counts(task_id: str) -> dict:
    """
    根据子任务实际状态重新计算并同步任务的 completed_count、failed_count。
    用于修复因重复提交导致的计数错误（如 pending_count 为负）。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return {"success": False, "message": "任务不存在"}

    counts = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM sub_tasks WHERE task_id = ? GROUP BY status",
        (task_id,),
    ).fetchall()

    completed = sum(c["cnt"] for c in counts if c["status"] == "completed")
    failed = sum(c["cnt"] for c in counts if c["status"] == "failed")

    conn.execute(
        "UPDATE tasks SET completed_count = ?, failed_count = ?, updated_at = ? WHERE id = ?",
        (completed, failed, datetime.datetime.now().isoformat(), task_id),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "completed_count": completed,
        "failed_count": failed,
        "message": f"已同步: completed={completed}, failed={failed}",
    }


def resume_task(task_id: str) -> dict:
    """
    恢复执行指定任务中所有未完成的子任务（pending 或 running）。
    将 running 重置为 pending 后重新提交到线程池。
    用于手动触发继续执行卡住的子任务。

    Returns:
        包含 success, resumed_count, message 的字典
    """
    task_log = get_task_logger(task_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return {"success": False, "resumed_count": 0, "message": "任务不存在"}

    pending_subs = conn.execute(
        "SELECT id, feature_name FROM sub_tasks WHERE task_id = ? AND status IN ('pending', 'running')",
        (task_id,),
    ).fetchall()

    if not pending_subs:
        conn.close()
        return {"success": True, "resumed_count": 0, "message": "没有待执行的子任务"}

    resumed_count = len(pending_subs)
    now = datetime.datetime.now().isoformat()

    conn.execute(
        "UPDATE sub_tasks SET status = 'pending' WHERE task_id = ? AND status = 'running'",
        (task_id,),
    )
    conn.execute(
        "UPDATE tasks SET status = 'running', finished_at = NULL, result_file = NULL, updated_at = ? WHERE id = ?",
        (now, task_id),
    )
    conn.commit()
    conn.close()

    task_log.info("恢复执行 %d 个未完成的子任务", resumed_count)

    if _executor:
        for sub in pending_subs:
            _executor.submit(_process_sub_task, task_id, sub["id"])
            task_log.info("重新提交子任务: [%s] %s", sub["id"], sub["feature_name"])

    return {
        "success": True,
        "resumed_count": resumed_count,
        "message": f"已重新提交 {resumed_count} 个未完成的子任务",
    }


def recover_tasks():
    """
    服务启动时恢复未完成的任务。
    将所有 pending 或 running 状态的子任务重新提交到线程池。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    running_tasks = conn.execute(
        "SELECT id FROM tasks WHERE status = 'running'"
    ).fetchall()

    total_recovered = 0
    for task in running_tasks:
        task_id = task["id"]
        task_log = get_task_logger(task_id)

        pending_subs = conn.execute(
            "SELECT id, feature_name FROM sub_tasks WHERE task_id = ? AND status IN ('pending', 'running')",
            (task_id,),
        ).fetchall()

        if pending_subs:
            conn.execute(
                "UPDATE sub_tasks SET status = 'pending' WHERE task_id = ? AND status = 'running'",
                (task_id,),
            )
            conn.commit()

            for sub in pending_subs:
                if _executor:
                    _executor.submit(_process_sub_task, task_id, sub["id"])
                    total_recovered += 1
                    task_log.info("恢复子任务: [%s] %s", sub["id"], sub["feature_name"])

    conn.close()
    if total_recovered > 0:
        logger.info("已恢复 %d 个未完成的子任务", total_recovered)
    else:
        logger.info("没有需要恢复的任务")
