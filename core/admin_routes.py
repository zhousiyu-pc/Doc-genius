"""
管理后台 REST API
================
用户管理、数据统计、套餐管理。
需要管理员权限（通过 ADMIN_USERS 环境变量配置）。
"""

import os
import logging
import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.auth import get_user_from_request
from core.db import get_db

logger = logging.getLogger("agent_skills.admin")

# 管理员用户名列表（逗号分隔）
ADMIN_USERS = set(
    u.strip()
    for u in os.environ.get("ADMIN_USERS", "admin").split(",")
    if u.strip()
)


def _require_admin(request: Request):
    """验证管理员权限，返回 (user, error_response)。"""
    user = get_user_from_request(request)
    if not user:
        return None, JSONResponse(
            {"success": False, "message": "需要登录"}, status_code=401
        )
    if user["username"] not in ADMIN_USERS:
        return None, JSONResponse(
            {"success": False, "message": "权限不足"}, status_code=403
        )
    return user, None


async def api_admin_stats(request: Request) -> JSONResponse:
    """GET /api/admin/stats — 数据概览"""
    user, err = _require_admin(request)
    if err:
        return err

    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sessions = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
        total_messages = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]

        # 活跃订阅数
        now = datetime.datetime.now().isoformat()
        try:
            active_subs = conn.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND expires_at > ?",
                (now,),
            ).fetchone()[0]
        except Exception:
            active_subs = 0

    return JSONResponse({
        "success": True,
        "stats": {
            "total_users": total_users,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "active_subscriptions": active_subs,
        },
    })


async def api_admin_users(request: Request) -> JSONResponse:
    """GET /api/admin/users — 用户列表"""
    user, err = _require_admin(request)
    if err:
        return err

    today = datetime.date.today().isoformat()
    month_start = datetime.date.today().replace(day=1).isoformat()

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()

        users = []
        for row in rows:
            uid = row["id"]

            # 会话数
            sc = conn.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE user_id = ?", (uid,)
            ).fetchone()[0]

            # 套餐
            now = datetime.datetime.now().isoformat()
            try:
                sub = conn.execute(
                    "SELECT p.display_name FROM subscriptions s JOIN plans p ON s.plan_id = p.id "
                    "WHERE s.user_id = ? AND s.status = 'active' AND s.expires_at > ? "
                    "ORDER BY s.expires_at DESC LIMIT 1",
                    (uid, now),
                ).fetchone()
                plan_name = sub[0] if sub else "免费版"
            except Exception:
                plan_name = "免费版"

            # 今日对话
            try:
                ur = conn.execute(
                    "SELECT chat_count, doc_count FROM usage_records WHERE user_id = ? AND record_date = ?",
                    (uid, today),
                ).fetchone()
                today_chat = ur["chat_count"] if ur else 0
                month_doc = 0
                # 本月文档
                month_rows = conn.execute(
                    "SELECT SUM(doc_count) FROM usage_records WHERE user_id = ? AND record_date >= ?",
                    (uid, month_start),
                ).fetchone()
                month_doc = month_rows[0] or 0 if month_rows else 0
            except Exception:
                today_chat = 0
                month_doc = 0

            users.append({
                "id": uid,
                "username": row["username"],
                "created_at": row["created_at"],
                "session_count": sc,
                "plan_name": plan_name,
                "today_chat": today_chat,
                "month_doc": month_doc,
            })

    return JSONResponse({"success": True, "users": users})


admin_routes = [
    Route("/api/admin/stats", api_admin_stats, methods=["GET"]),
    Route("/api/admin/users", api_admin_users, methods=["GET"]),
]
