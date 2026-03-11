"""
任务管理 Skill — 核心业务逻辑（优化版）
======================================
集成需求分析引擎，支持智能文档生成。
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
from typing import Optional

from ...core.config import (
    TASK_WORKERS, MAX_RETRIES, RETRY_INTERVALS,
    LLM_API_KEY, DB_PATH,
)
from ...core.db import get_db
from ...core.llm_client import call_completion
from ...core.logger import get_task_logger
from ...core.analyzer import RequirementAnalyzer, analyze_requirement
from ..file_saver.service import save_file

logger = logging.getLogger("agent_skills.task_manager")

_executor: Optional[ThreadPoolExecutor] = None
_shutdown_event = threading.Event()


# ── 优化版文档模板（5W2H + 测试驱动）──────────────────────────

_FEATURE_TEMPLATE = """### {feature_name}

#### 1. Why - 业务背景
- **业务目标**：{business_goal}
- **用户价值**：{user_value}
- **使用角色**：{user_roles}
- **使用频率**：{usage_frequency}
- **优先级**：{priority}

#### 2. What - 功能说明
- **功能概述**：{feature_overview}
- **前置条件**：{prerequisites}
- **后置结果**：{post_conditions}
- **业务规则**：
{business_rules}

#### 3. Input - 输入设计
##### 3.1 用户输入
| 字段名 | 类型 | 必填 | 默认值 | 校验规则 | 说明 |
|--------|------|------|--------|----------|------|
{user_inputs}

##### 3.2 系统输入
{system_inputs}

#### 4. Output - 输出设计
##### 4.1 用户可见输出
{user_outputs}

##### 4.2 系统输出
{system_outputs}

#### 5. How - 功能流程
##### 5.1 用户操作流程
{user_flow}

##### 5.2 系统处理流程
{system_flow}

##### 5.3 状态流转
| 当前状态 | 触发事件 | 目标状态 | 说明 |
|----------|----------|----------|------|
{state_transitions}

#### 6. Interface - 接口设计
##### 6.1 内部 API
| 接口 | 方法 | 路径 | 请求参数 | 响应结构 |
|------|------|------|----------|----------|
{internal_apis}

##### 6.2 外部 API
{external_apis}

##### 6.3 数据模型
```
{data_models}
```

#### 7. Test - 测试覆盖
##### 7.1 功能测试用例
| 编号 | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|------|------|----------|----------|----------|--------|
{test_cases}

##### 7.2 边界测试
{boundary_tests}

##### 7.3 异常场景
| 异常场景 | 触发条件 | 系统处理 | 用户提示 |
|----------|----------|----------|----------|
{exception_scenarios}

##### 7.4 性能要求
- **响应时间**：{response_time}
- **并发支持**：{concurrency}
- **数据量级**：{data_scale}

#### 8. Security - 安全设计
- **权限控制**：{permissions}
- **数据脱敏**：{data_masking}
- **操作审计**：{audit_log}

#### 9. Notes - 特殊说明
{special_notes}

---
"""

_DOC_TEMPLATE = """# {project_name} - 需求规格说明书

> 文档版本：1.0  
> 生成时间：{generated_time}  
> 复杂度：{complexity} | 预估功能点：{feature_count}

---

## 一、项目概述

### 1.1 业务背景
{project_summary}

### 1.2 产品定位
- **业务模式**：{business_model}
- **目标市场**：{target_market}
- **对接平台**：{platforms}

### 1.3 跨境电商特有考虑
{cross_border_notes}

### 1.4 合规要求
{compliance_notes}

## 二、系统架构

### 2.1 整体架构图
```mermaid
{architecture_diagram}
```

### 2.2 技术选型建议
| 层级 | 推荐技术 | 说明 |
|------|----------|------|
| 前端 | Vue3 / React | 响应式设计，支持多语言 |
| 后端 | Python FastAPI / Node.js | 高并发 API 服务 |
| 数据库 | PostgreSQL / MySQL | 支持事务和多币种 |
| 缓存 | Redis | 会话和热点数据缓存 |
| 消息队列 | RabbitMQ / Kafka | 异步任务处理 |

### 2.3 部署架构
- **部署方式**：Docker 容器化部署
- **环境**：开发/测试/生产三环境隔离
- **监控**：Prometheus + Grafana

## 三、功能模块总览

{module_overview}

## 四、功能点详细设计

{feature_details_text}

## 五、数据模型

### 5.1 ER 图
```mermaid
{er_diagram}
```

### 5.2 核心表结构
{table_structures}

## 六、接口设计

### 6.1 内部 API 清单
{api_list}

### 6.2 外部 API 集成
{external_integrations}

## 七、测试计划

### 7.1 测试策略
- 单元测试覆盖率：>80%
- 集成测试：核心流程 100% 覆盖
- 性能测试：支持 {concurrency_target} 并发

### 7.2 测试用例汇总
{test_summary}

## 八、项目计划

### 8.1 阶段划分
| 阶段 | 周期 | 交付物 |
|------|------|--------|
| Phase 1 | 2-3 周 | 核心模块（商品 + 订单） |
| Phase 2 | 2-3 周 | 物流 + 仓储模块 |
| Phase 3 | 2 周 | 财务 + 报表模块 |
| Phase 4 | 1-2 周 | 系统集成测试 |

### 8.2 风险评估
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| API 限流 | 中 | 高 | 实现请求队列和退避重试 |
| 数据一致性 | 中 | 高 | 分布式事务和补偿机制 |
| 需求变更 | 高 | 中 | 敏捷迭代，快速响应 |

## 九、附录

### 9.1 术语表
| 术语 | 说明 |
|------|------|
| SKU | 库存量单位 |
| FBA | Fulfillment by Amazon |
| VAT | 增值税 |

### 9.2 参考资料
- [Amazon SP-API 文档](https://developer-docs.amazon.com/sp-api)
- [TikTok Shop API 文档](https://partner.tiktokshop.com/docv2/page)

---

_本文档由 Agent Skills Server 智能生成_
"""


# ── 执行器管理 ──────────────────────────────────────

def init_executor():
    """初始化线程池"""
    global _executor
    _executor = ThreadPoolExecutor(
        max_workers=TASK_WORKERS,
        thread_name_prefix="task-worker",
    )
    logger.info("线程池已创建，并发 Worker 数：%d", TASK_WORKERS)


def shutdown_executor():
    """关闭线程池"""
    global _executor
    _shutdown_event.set()
    if _executor:
        _executor.shutdown(wait=False)
        logger.info("线程池已关闭")


# ── 子任务处理 ──────────────────────────────────────

def _process_sub_task(task_id: str, sub_task_id: str):
    """
    处理单个子任务：调用 LLM API 生成功能点详设。
    使用优化版 5W2H + 测试驱动模板。
    """
    task_log = get_task_logger(task_id)

    with get_db() as conn:
        row = conn.execute(
            "SELECT feature_name, retry_count, status FROM sub_tasks WHERE id = ?",
            (sub_task_id,),
        ).fetchone()
        if not row:
            task_log.error("子任务不存在：%s", sub_task_id)
            return
        if row["status"] in ("completed", "failed"):
            task_log.debug("子任务已终态，跳过：[%s] status=%s", sub_task_id, row["status"])
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

    task_log.info("开始处理功能点：[%s] (重试次数：%d)", feature_name, current_retry)

    # 解析上下文
    llm_context = task_row["context"]
    doc_context = {}
    try:
        ctx_obj = json.loads(llm_context)
        if isinstance(ctx_obj, dict):
            doc_context = ctx_obj
            llm_context = ctx_obj.get("_llm_context", llm_context)
    except (json.JSONDecodeError, TypeError):
        pass

    # 构建 Prompt（使用优化版模板）
    system_prompt = """你是资深的跨境电商 ERP 系统架构师兼产品经理。
你需要针对给定的功能点，输出一份完整的功能详细设计文档。

请严格按照以下 5W2H + 测试驱动的格式输出，每个章节都必须填写具体内容：

1. Why - 业务背景（目标、价值、角色、频率、优先级）
2. What - 功能说明（概述、前置条件、后置结果、业务规则）
3. Input - 输入设计（用户输入表格、系统输入）
4. Output - 输出设计（用户可见输出、系统输出）
5. How - 功能流程（用户操作流程、系统处理流程、状态流转表）
6. Interface - 接口设计（内部 API 表、外部 API、数据模型）
7. Test - 测试覆盖（功能测试用例表、边界测试、异常场景表、性能要求）
8. Security - 安全设计（权限、脱敏、审计）
9. Notes - 特殊说明（跨境特性、技术难点）

要求：
- 所有内容必须结合项目背景具体展开，不要写通用模板
- 功能测试用例至少 5 条，覆盖正常流程和异常流程
- 接口设计要给出具体的请求参数和响应结构
- 数据模型要列出具体的字段名和类型
- 业务规则至少 3 条
- 用表格和结构化格式提升可读性"""

    user_message = (
        f"请为以下功能点撰写完整的详细设计文档：\n\n"
        f"## 功能点名称\n{feature_name}\n\n"
        f"## 项目背景\n{llm_context}\n\n"
        f"## 背景信息\n"
        f"- 业务模式：{task_row['business_model'] or 'B2C 零售'}\n"
        f"- 目标市场：{task_row['target_market'] or '全球'}\n"
        f"- 对接平台：{task_row['platforms'] or '未指定'}\n"
        f"- 文档详细程度：{task_row['detail_level'] or '详细'}\n\n"
        f"请严格按照系统提示词中的 5W2H + 测试驱动格式输出，"
        f"所有章节都必须结合以上项目背景具体展开。"
    )

    try:
        result_text = call_completion(
            feature_name=feature_name,
            project_context=user_message,
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

        task_log.info("功能点完成：[%s] (结果长度：%d 字符)", feature_name, len(result_text))
        _check_task_completion(task_id, task_log)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        task_log.error("功能点失败：[%s] 错误：%s", feature_name, error_msg)

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
                "功能点最终失败（已达最大重试次数）: [%s] 错误：%s",
                feature_name, error_msg,
            )
            _check_task_completion(task_id, task_log)


def _check_task_completion(task_id: str, task_log: logging.Logger):
    """检查整个任务是否全部完成"""
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
                "任务完成！状态：%s, 成功：%d, 失败：%d, 总计：%d",
                final_status, row["completed_count"], row["failed_count"], row["total_count"],
            )

            _auto_assemble_and_save(task_id, task_log)


def _auto_assemble_and_save(task_id: str, task_log: logging.Logger):
    """任务完成后自动汇总所有子任务结果，生成最终文档"""
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

        # 收集所有功能点结果
        results = []
        for s in sub_tasks:
            if s["status"] == "completed" and s["result"]:
                results.append(s["result"])
            elif s["status"] == "failed":
                results.append(f"### {s['feature_name']}\n\n> 该功能点生成失败，请稍后重试。\n\n---")

        feature_details_text = "\n\n".join(results)

        # 解析文档上下文
        doc_context = {}
        try:
            doc_context = json.loads(task["context"]) if task["context"].strip().startswith("{") else {}
        except (json.JSONDecodeError, AttributeError):
            pass

        project_name = doc_context.get("project_name", "跨境电商 ERP 系统")
        save_directory = doc_context.get("save_directory", "")
        
        # 生成模块总览表格
        core_modules = doc_context.get("core_modules", [])
        feature_list = doc_context.get("feature_list", [])
        module_overview = "| 模块 | 功能点数量 | 核心功能 |\n|------|------------|----------|\n"
        for module in core_modules:
            module_features = [f for f in feature_list if module in f]
            module_overview += f"| {module} | {len(module_features)} | {', '.join(module_features[:3])} |\n"

        # 生成最终文档
        markdown = _DOC_TEMPLATE.format(
            project_name=project_name,
            generated_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            complexity=doc_context.get("complexity", "中等"),
            feature_count=doc_context.get("estimated_features", len(feature_list)),
            project_summary=doc_context.get("project_summary", ""),
            business_model=doc_context.get("business_model", task["business_model"] or "B2C 零售"),
            target_market=doc_context.get("target_market", task["target_market"] or "全球"),
            platforms=doc_context.get("platforms", task["platforms"] or "未指定"),
            cross_border_notes=doc_context.get("cross_border_notes", "无特殊考虑"),
            compliance_notes=doc_context.get("compliance_notes", "基础合规检查"),
            architecture_diagram=doc_context.get("architecture_diagram", "graph TB\n    User[用户] --> Frontend[前端]\n    Frontend --> API[API 服务]"),
            module_overview=module_overview,
            feature_details_text=feature_details_text,
            er_diagram=doc_context.get("er_diagram", "待补充"),
            table_structures=doc_context.get("table_structures", "待详细设计阶段补充"),
            api_list=doc_context.get("api_list", "待详细设计阶段补充"),
            external_integrations=doc_context.get("external_integrations", "待详细设计阶段补充"),
            concurrency_target=doc_context.get("concurrency_target", "1000 QPS"),
            test_summary=doc_context.get("test_summary", "待测试阶段补充"),
        )

        # 生成文件名
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = project_name.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}_需求文档_{ts}.md"

        # 保存文件
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
            task_log.info("文档自动保存成功：%s", filepath)
        else:
            task_log.error("文档自动保存失败：%s", save_result.get("message", ""))

    except Exception as e:
        task_log.error("自动汇总保存出错：%s", str(e), exc_info=True)


# ── 任务提交接口 ──────────────────────────────────────

def submit_task_with_analysis(
    raw_requirement: str,
    save_directory: str = "",
    detail_level: str = "详细",
) -> dict:
    """
    【推荐接口】提交原始需求，自动分析并生成任务。
    
    Args:
        raw_requirement: 用户原始需求描述（自然语言）
        save_directory: 文件保存目录
        detail_level: 详细程度
    
    Returns:
        包含 task_id, feature_count, questions 等信息的字典
    """
    # 1. 智能分析需求
    analyzer = RequirementAnalyzer()
    analyzed = analyzer.analyze(raw_requirement)
    doc_context = analyzer.to_context_dict(analyzed)
    doc_context["save_directory"] = save_directory
    
    # 2. 提交任务
    task_id = submit_task(
        feature_list=analyzed.feature_list,
        context=raw_requirement,
        business_model=analyzed.business_model.value,
        target_market=analyzed.target_market,
        platforms=", ".join(analyzed.platforms),
        detail_level=detail_level,
        doc_context=doc_context,
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "feature_count": analyzed.estimated_features,
        "complexity": analyzed.complexity.value,
        "core_modules": analyzed.core_modules,
        "platforms": analyzed.platforms,
        "questions": analyzed.questions,  # 智能追问列表
        "message": f"已创建任务，将生成 {analyzed.estimated_features} 个功能点的详细需求文档",
    }


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
    提交一个新任务（传统接口，兼容旧代码）。
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

    task_log.info("任务创建成功：task_id=%s, 功能点数量=%d", task_id, len(feature_list))
    for feat in feature_list:
        task_log.info("  - %s", feat)
    if doc_context:
        task_log.info("文档上下文已保存，任务完成后将自动汇总并保存文件")

    if _executor:
        for sub_id in sub_task_ids:
            _executor.submit(_process_sub_task, task_id, sub_id)
        task_log.info("所有子任务已提交到线程池 (并发数：%d)", TASK_WORKERS)

    return task_id


# ── 任务管理接口 ──────────────────────────────────────

def retry_failed_task(task_id: str) -> dict:
    """重试指定任务中所有失败的子任务"""
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
            task_log.info("重新提交子任务：[%s] %s", sub["id"], sub["feature_name"])

    return {
        "success": True,
        "retried_count": retried_count,
        "message": f"已重新提交 {retried_count} 个失败的子任务",
    }


def resume_task(task_id: str) -> dict:
    """恢复执行指定任务中所有未完成的子任务"""
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
            task_log.info("重新提交子任务：[%s] %s", sub["id"], sub["feature_name"])

    return {
        "success": True,
        "resumed_count": resumed_count,
        "message": f"已重新提交 {resumed_count} 个未完成的子任务",
    }


def recover_tasks():
    """服务启动时恢复未完成的任务"""
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
                    task_log.info("恢复子任务：[%s] %s", sub["id"], sub["feature_name"])

    conn.close()
    if total_recovered > 0:
        logger.info("已恢复 %d 个未完成的子任务", total_recovered)
    else:
        logger.info("没有需要恢复的任务")
