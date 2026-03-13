"""
任务管理 Skill — REST API 路由（通用版）
======================================
支持多领域文档生成，不依赖 Dify。
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.config import LLM_API_KEY
from core.db import get_db
from core.analyzer import analyze_requirement
from skills.task_manager import service as task_service

logger = logging.getLogger("agent_skills.task_manager")


async def api_analyze_requirement(request: Request) -> JSONResponse:
    """
    POST /api/analyze — 智能分析需求并创建任务（推荐接口）
    
    用户只需输入自然语言需求，系统自动分析领域、拆解功能点并生成文档。
    
    请求体 JSON：
    {
        "requirement": "我想做一个 CRM 系统，管理客户信息、销售跟进",
        "options": {
            "detail_level": "标准",  // 简洁/标准/详细
            "output_format": "markdown"  // markdown/pdf/word
        }
    }
    
    响应示例：
    {
        "success": true,
        "task_id": "a1b2c3d4e5f6",
        "domain": "crm",
        "domain_name": "CRM 系统",
        "feature_count": 16,
        "complexity": "中等",
        "core_modules": ["客户管理", "销售管理", "合同管理"],
        "questions": [
            {
                "field": "user_scale",
                "question": "预计用户数量？",
                "options": ["<50 人", "50-200 人", "200-500 人"]
            }
        ],
        "message": "已创建任务，将生成 16 个功能点的详细需求文档"
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "message": "请求体必须为有效的 JSON"},
            status_code=400,
        )

    requirement = body.get("requirement", "")
    if not requirement:
        return JSONResponse(
            {"success": False, "message": "requirement 不能为空"},
            status_code=400,
        )
    # 预览模式仅做需求分析，不真正调用 LLM 生成详细文档
    preview_only = bool(body.get("preview_only"))
    if not preview_only and not LLM_API_KEY:
        return JSONResponse(
            {"success": False, "message": "LLM_API_KEY 未配置，请设置环境变量"},
            status_code=500,
        )

    try:
        logger.info("收到需求分析请求: requirement=%s", requirement)

        # 1) 仅预览：返回分析结果和功能大纲，不创建任务
        if preview_only:
            from core.analyzer import RequirementAnalyzer

            analyzer = RequirementAnalyzer()
            analyzed = analyzer.analyze(requirement)
            ctx = analyzer.to_context_dict(analyzed)

            return JSONResponse(
                {
                    "success": True,
                    "preview_only": True,
                    "domain": analyzed.domain.value,
                    "domain_name": analyzed.domain_name,
                    "feature_count": analyzed.estimated_features,
                    "complexity": analyzed.complexity.value,
                    "core_modules": analyzed.core_modules,
                    "feature_list": analyzed.feature_list,
                    "questions": analyzed.questions,
                    "context": ctx,
                    "message": "已生成需求大纲，请确认后再生成详细文档",
                }
            )

        # 2) 正式生成：分析 + 创建任务
        result = task_service.submit_task_with_analysis(
            raw_requirement=requirement,
            save_directory=body.get("save_directory", ""),
            detail_level=body.get("options", {}).get("detail_level", "标准"),
        )
        
        # 添加领域信息到响应（如前端有额外传入，可透传）
        result["domain"] = body.get("domain", "") or result.get("domain", "")
        
        return JSONResponse(result)
    
    except Exception as e:
        logger.exception("需求分析失败: %s", str(e))
        # 对常见错误给出更友好的提示
        err_msg = str(e)
        if "LLM_API_KEY" in err_msg or "api_key" in err_msg.lower():
            user_msg = "LLM API Key 未配置或无效，请设置环境变量 LLM_API_KEY"
        elif "connection" in err_msg.lower() or "timeout" in err_msg.lower():
            user_msg = "无法连接 LLM 服务，请检查网络或稍后重试"
        elif "permission" in err_msg.lower() or "Permission" in err_msg:
            user_msg = "数据库或文件权限不足，请检查数据目录可写性"
        else:
            user_msg = f"分析失败：{err_msg}"
        return JSONResponse(
            {"success": False, "message": user_msg},
            status_code=500,
        )


async def api_submit_task(request: Request) -> JSONResponse:
    """
    POST /api/tasks — 提交新任务（传统接口，兼容旧代码）
    
    请求体 JSON：
    {
        "feature_list": ["模块 A-功能 1", "模块 A-功能 2", ...],
        "context": "项目整体背景描述",
        "business_model": "B2C 零售",
        "target_market": "北美",
        "platforms": "Amazon, Shopify",
        "detail_level": "详细"
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "message": "请求体必须为有效的 JSON"},
            status_code=400,
        )

    feature_list = body.get("feature_list", [])
    context = body.get("context", "")

    if not feature_list:
        return JSONResponse({"success": False, "message": "feature_list 不能为空"}, status_code=400)
    if not context:
        return JSONResponse({"success": False, "message": "context 不能为空"}, status_code=400)
    if not LLM_API_KEY:
        return JSONResponse(
            {"success": False, "message": "LLM_API_KEY 未配置，请设置环境变量"},
            status_code=500,
        )

    task_id = task_service.submit_task(
        feature_list=feature_list,
        context=context,
        business_model=body.get("business_model", ""),
        target_market=body.get("target_market", ""),
        platforms=body.get("platforms", ""),
        detail_level=body.get("detail_level", "详细"),
        doc_context=body.get("doc_context"),
    )

    return JSONResponse({
        "success": True,
        "task_id": task_id,
        "total_count": len(feature_list),
        "message": f"任务已提交，共 {len(feature_list)} 个功能点",
    })


async def api_task_status(request: Request) -> JSONResponse:
    """GET /api/tasks/{task_id} — 查询任务状态"""
    task_id = request.path_params["task_id"]
    try:
        with get_db() as conn:
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                return JSONResponse({"success": False, "message": "任务不存在"}, status_code=404)

            sub_tasks = conn.execute(
                "SELECT id, feature_name, seq_index, status, retry_count, error_message, started_at, finished_at "
                "FROM sub_tasks WHERE task_id = ? ORDER BY seq_index",
                (task_id,),
            ).fetchall()

        result_file = ""
        try:
            result_file = task["result_file"] or ""
        except (IndexError, KeyError):
            pass

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "status": task["status"],
            "total_count": task["total_count"],
            "completed_count": task["completed_count"],
            "failed_count": task["failed_count"],
            "pending_count": max(0, task["total_count"] - task["completed_count"] - task["failed_count"]),
            "result_file": result_file,
            "created_at": task["created_at"],
            "finished_at": task["finished_at"],
            "sub_tasks": [
                {
                    "id": s["id"],
                    "feature_name": s["feature_name"],
                    "index": s["seq_index"],
                    "status": s["status"],
                    "retry_count": s["retry_count"],
                    "error": s["error_message"],
                }
                for s in sub_tasks
            ],
        })
    except Exception as e:
        logger.exception("查询任务状态失败: task_id=%s", task_id)
        return JSONResponse(
            {"success": False, "message": f"查询失败：{str(e)}"},
            status_code=500,
        )


def _build_results_response(task_id: str) -> dict | None:
    """构建任务结果响应"""
    with get_db() as conn:
        task = conn.execute(
            "SELECT status, total_count, completed_count, failed_count, result_file FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not task:
            return None

        sub_tasks = conn.execute(
            "SELECT feature_name, seq_index, status, result FROM sub_tasks "
            "WHERE task_id = ? ORDER BY seq_index",
            (task_id,),
        ).fetchall()

    results = []
    for s in sub_tasks:
        if s["status"] == "completed" and s["result"]:
            results.append(s["result"])
        elif s["status"] == "failed":
            results.append(f"### {s['feature_name']}\n\n> 该功能点生成失败，请稍后重试。\n\n---")
        else:
            results.append("")

    is_done = task["status"] in ("completed", "partial")

    return {
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "is_done": is_done,
        "total_count": task["total_count"],
        "completed_count": task["completed_count"],
        "failed_count": task["failed_count"],
        "result_file": task["result_file"] or "",
        "results": results,
    }


async def api_task_results(request: Request) -> JSONResponse:
    """GET /api/tasks/{task_id}/result — 获取任务结果"""
    task_id = request.path_params["task_id"]

    data = _build_results_response(task_id)
    if data is None:
        return JSONResponse({"success": False, "message": "任务不存在"}, status_code=404)

    return JSONResponse(data)


async def api_retry_failed(request: Request) -> JSONResponse:
    """POST /api/tasks/{task_id}/retry — 重试失败的子任务"""
    task_id = request.path_params["task_id"]
    result = task_service.retry_failed_task(task_id)
    status_code = 200 if result["success"] else 404
    return JSONResponse(result, status_code=status_code)


async def api_resume_task(request: Request) -> JSONResponse:
    """POST /api/tasks/{task_id}/resume — 恢复执行未完成的任务"""
    task_id = request.path_params["task_id"]
    result = task_service.resume_task(task_id)
    status_code = 200 if result["success"] else 404
    return JSONResponse(result, status_code=status_code)


async def api_cancel_task(request: Request) -> JSONResponse:
    """POST /api/tasks/{task_id}/cancel — 取消任务生成"""
    task_id = request.path_params["task_id"]
    result = task_service.cancel_task(task_id)
    status_code = 200 if result["success"] else 404
    return JSONResponse(result, status_code=status_code)


routes = [
    # 🆕 智能分析接口（推荐，通用版）
    Route("/api/analyze", api_analyze_requirement, methods=["POST"]),
    
    # 传统接口（兼容）
    Route("/api/tasks", api_submit_task, methods=["POST"]),
    Route("/api/tasks/{task_id}", api_task_status, methods=["GET"]),
    Route("/api/tasks/{task_id}/result", api_task_results, methods=["GET"]),
    Route("/api/tasks/{task_id}/retry", api_retry_failed, methods=["POST"]),
    Route("/api/tasks/{task_id}/resume", api_resume_task, methods=["POST"]),
    Route("/api/tasks/{task_id}/cancel", api_cancel_task, methods=["POST"]),
]
