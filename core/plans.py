"""
套餐与配额管理模块
=================
内置套餐初始化、用户套餐查询、配额检查与用量记录。
"""

import json
import uuid
import logging
import datetime

from .db import get_db

logger = logging.getLogger("agent_skills.plans")

# 所有可用模型列表
ALL_MODELS = [
    "qwen-plus", "deepseek-chat", "qwen-max",
    "gpt-4o", "claude-sonnet", "gpt-4o-mini",
    "deepseek-reasoner", "qwen-turbo",
]

# 内置套餐定义
_BUILTIN_PLANS = [
    {
        "id": "free",
        "name": "free",
        "display_name": "免费版",
        "price_monthly": 0,
        "price_quarterly": 0,
        "price_yearly": 0,
        "daily_chat_limit": 10,
        "monthly_doc_limit": 3,
        "max_file_size_mb": 5,
        "max_versions": 0,
        "allowed_models": json.dumps(["qwen-plus", "deepseek-chat"]),
        "features": json.dumps([
            "10次对话/天",
            "3篇文档/月",
            "基础模型(通义千问/DeepSeek)",
            "Word导出",
            "5MB文件上传",
        ]),
        "sort_order": 0,
    },
    {
        "id": "pro",
        "name": "pro",
        "display_name": "专业版",
        "price_monthly": 4900,
        "price_quarterly": 13230,
        "price_yearly": 41160,
        "daily_chat_limit": 100,
        "monthly_doc_limit": 50,
        "max_file_size_mb": 20,
        "max_versions": 5,
        "allowed_models": json.dumps(["qwen-plus", "deepseek-chat", "qwen-max", "gpt-4o", "claude-sonnet"]),
        "features": json.dumps([
            "100次对话/天",
            "50篇文档/月",
            "高级模型(GPT-4o/Claude)",
            "Word+PDF导出",
            "20MB文件上传",
            "5个版本快照",
            "文档分享",
            "历史永久保留",
        ]),
        "sort_order": 1,
    },
    {
        "id": "team",
        "name": "team",
        "display_name": "团队版",
        "price_monthly": 19900,
        "price_quarterly": 53730,
        "price_yearly": 167160,
        "daily_chat_limit": 500,
        "monthly_doc_limit": 200,
        "max_file_size_mb": 50,
        "max_versions": -1,
        "allowed_models": json.dumps(ALL_MODELS),
        "features": json.dumps([
            "500次对话/天",
            "200篇文档/月",
            "全部模型",
            "Word+PDF+PPT导出",
            "50MB文件上传",
            "无限版本快照",
            "团队协作",
            "优先客服支持",
        ]),
        "sort_order": 2,
    },
    {
        "id": "enterprise",
        "name": "enterprise",
        "display_name": "企业版",
        "price_monthly": 99900,
        "price_quarterly": 269730,
        "price_yearly": 839160,
        "daily_chat_limit": -1,
        "monthly_doc_limit": -1,
        "max_file_size_mb": 100,
        "max_versions": -1,
        "allowed_models": json.dumps(ALL_MODELS),
        "features": json.dumps([
            "无限对话",
            "无限文档",
            "全部模型+私有部署",
            "全格式导出+API",
            "100MB文件上传",
            "无限版本",
            "SSO集成",
            "专属客户经理",
            "SLA保障",
        ]),
        "sort_order": 3,
    },
]


def init_builtin_plans():
    """初始化四个内置套餐（不存在则插入，已存在则更新 features）。"""
    now = datetime.datetime.now().isoformat()
    with get_db() as conn:
        for plan in _BUILTIN_PLANS:
            existing = conn.execute(
                "SELECT id FROM plans WHERE id = ?", (plan["id"],)
            ).fetchone()
            if existing:
                # 更新 features 和价格（保持数据最新）
                conn.execute(
                    "UPDATE plans SET features = ?, price_monthly = ?, price_quarterly = ?, "
                    "price_yearly = ?, daily_chat_limit = ?, monthly_doc_limit = ?, "
                    "max_file_size_mb = ?, max_versions = ?, allowed_models = ?, display_name = ? "
                    "WHERE id = ?",
                    (
                        plan["features"], plan["price_monthly"],
                        plan["price_quarterly"], plan["price_yearly"],
                        plan["daily_chat_limit"], plan["monthly_doc_limit"],
                        plan["max_file_size_mb"], plan["max_versions"],
                        plan["allowed_models"], plan["display_name"],
                        plan["id"],
                    ),
                )
                continue
            conn.execute(
                "INSERT INTO plans "
                "(id, name, display_name, price_monthly, price_quarterly, price_yearly, "
                "daily_chat_limit, monthly_doc_limit, max_file_size_mb, max_versions, "
                "allowed_models, features, sort_order, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    plan["id"], plan["name"], plan["display_name"],
                    plan["price_monthly"], plan["price_quarterly"], plan["price_yearly"],
                    plan["daily_chat_limit"], plan["monthly_doc_limit"],
                    plan["max_file_size_mb"], plan["max_versions"],
                    plan["allowed_models"], plan["features"],
                    plan["sort_order"], now,
                ),
            )
    logger.info("内置套餐初始化完成")


def _row_to_dict(row) -> dict:
    """将 sqlite3.Row 转为普通 dict。"""
    if row is None:
        return None
    return dict(row)


def list_plans() -> list[dict]:
    """列出所有活跃套餐，按 sort_order 排序。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM plans WHERE is_active = 1 ORDER BY sort_order"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_plan(plan_id: str) -> dict | None:
    """获取单个套餐。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
    return _row_to_dict(row)


def get_user_plan(user_id: str) -> dict:
    """
    获取用户当前套餐信息。
    无有效订阅则返回 free 套餐。
    返回 {"plan": {...}, "subscription": {...} | None, "usage": {...}}
    """
    now = datetime.datetime.now().isoformat()
    subscription = None
    plan = None

    with get_db() as conn:
        # 查找 active 且未过期的最新订阅
        row = conn.execute(
            "SELECT * FROM subscriptions "
            "WHERE user_id = ? AND status = 'active' AND expires_at > ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, now),
        ).fetchone()

        if row:
            subscription = _row_to_dict(row)
            plan_row = conn.execute(
                "SELECT * FROM plans WHERE id = ?", (subscription["plan_id"],)
            ).fetchone()
            if plan_row:
                plan = _row_to_dict(plan_row)

    # 无有效订阅或找不到套餐 → free
    if plan is None:
        plan = get_plan("free")
        subscription = None

    usage = get_user_usage(user_id)

    return {
        "plan": plan,
        "subscription": subscription,
        "usage": usage,
    }


def _get_today() -> str:
    """返回今日日期字符串 YYYY-MM-DD。"""
    return datetime.date.today().isoformat()


def _get_month_start() -> str:
    """返回本月第一天 YYYY-MM-DD。"""
    today = datetime.date.today()
    return today.replace(day=1).isoformat()


def get_user_usage(user_id: str) -> dict:
    """
    获取用户今日和本月用量。
    返回 {
        "today": {"chat_count": N, "doc_count": N, "upload_count": N},
        "month": {"chat_count": N, "doc_count": N, "upload_count": N}
    }
    """
    today = _get_today()
    month_start = _get_month_start()

    with get_db() as conn:
        # 今日用量
        today_row = conn.execute(
            "SELECT chat_count, doc_count, upload_count FROM usage_records "
            "WHERE user_id = ? AND record_date = ?",
            (user_id, today),
        ).fetchone()

        # 本月用量（汇总）
        month_row = conn.execute(
            "SELECT COALESCE(SUM(chat_count), 0) as chat_count, "
            "COALESCE(SUM(doc_count), 0) as doc_count, "
            "COALESCE(SUM(upload_count), 0) as upload_count "
            "FROM usage_records "
            "WHERE user_id = ? AND record_date >= ?",
            (user_id, month_start),
        ).fetchone()

    today_usage = {
        "chat_count": today_row["chat_count"] if today_row else 0,
        "doc_count": today_row["doc_count"] if today_row else 0,
        "upload_count": today_row["upload_count"] if today_row else 0,
    }
    month_usage = {
        "chat_count": month_row["chat_count"] if month_row else 0,
        "doc_count": month_row["doc_count"] if month_row else 0,
        "upload_count": month_row["upload_count"] if month_row else 0,
    }

    return {"today": today_usage, "month": month_usage}


def check_quota(user_id: str, action: str) -> dict:
    """
    检查用户配额。

    Args:
        user_id: 用户 ID（匿名用户传 'anonymous'）
        action: "chat" | "doc" | "upload"

    Returns:
        {"allowed": bool, "remaining": int, "limit": int, "used": int}
    """
    user_plan = get_user_plan(user_id)
    plan = user_plan["plan"]
    usage = user_plan["usage"]

    if action == "chat":
        limit = plan["daily_chat_limit"]
        used = usage["today"]["chat_count"]
    elif action == "doc":
        limit = plan["monthly_doc_limit"]
        used = usage["month"]["doc_count"]
    elif action == "upload":
        # upload 共用 doc 的月度限额
        limit = plan["monthly_doc_limit"]
        used = usage["month"]["upload_count"]
    else:
        return {"allowed": False, "remaining": 0, "limit": 0, "used": 0}

    # -1 表示无限
    if limit == -1:
        return {"allowed": True, "remaining": -1, "limit": -1, "used": used}

    remaining = max(0, limit - used)
    allowed = used < limit

    return {"allowed": allowed, "remaining": remaining, "limit": limit, "used": used}


def record_usage(user_id: str, action: str):
    """
    记录使用量（+1），使用 UPSERT。

    Args:
        user_id: 用户 ID
        action: "chat" | "doc" | "upload"
    """
    today = _get_today()
    record_id = uuid.uuid4().hex[:12]

    column_map = {
        "chat": "chat_count",
        "doc": "doc_count",
        "upload": "upload_count",
    }
    column = column_map.get(action)
    if not column:
        logger.warning("未知的用量类型: %s", action)
        return

    with get_db() as conn:
        conn.execute(
            f"INSERT INTO usage_records (id, user_id, record_date, {column}) "
            f"VALUES (?, ?, ?, 1) "
            f"ON CONFLICT(user_id, record_date) DO UPDATE SET {column} = {column} + 1",
            (record_id, user_id, today),
        )


def check_model_access(user_id: str, model: str) -> bool:
    """
    检查用户是否有权使用某个模型。

    Args:
        user_id: 用户 ID
        model: 模型名称

    Returns:
        True 表示允许，False 表示不允许
    """
    user_plan = get_user_plan(user_id)
    plan = user_plan["plan"]

    allowed_models_str = plan.get("allowed_models", "")
    if not allowed_models_str:
        return False

    try:
        allowed_models = json.loads(allowed_models_str)
    except (json.JSONDecodeError, TypeError):
        return False

    return model in allowed_models
