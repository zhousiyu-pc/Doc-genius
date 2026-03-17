"""
文档分享模块
===========
生成分享链接，支持只读查看、密码保护、过期时间。
"""

import uuid
import secrets
import datetime
import json
import logging
from typing import Optional

from .db import get_db

logger = logging.getLogger("agent_skills.share")


def create_share_link(
    session_id: str,
    user_id: str = "",
    expires_hours: int = 0,
    password: str = "",
) -> dict:
    """
    为会话创建分享链接。

    Args:
        session_id: 会话 ID
        user_id: 创建者 ID
        expires_hours: 过期时间（小时），0 表示永不过期
        password: 访问密码，空表示无密码

    Returns:
        {"success": True, "share_id": "...", "token": "...", "url": "/share/..."}
    """
    with get_db() as conn:
        session = conn.execute(
            "SELECT id, title FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            return {"success": False, "message": "会话不存在"}

    share_id = uuid.uuid4().hex[:12]
    token = secrets.token_urlsafe(16)
    now = datetime.datetime.now().isoformat()

    expires_at = ""
    if expires_hours > 0:
        expires_at = (
            datetime.datetime.now() + datetime.timedelta(hours=expires_hours)
        ).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO share_links (id, session_id, user_id, token, expires_at, password, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (share_id, session_id, user_id, token, expires_at, password, now),
        )

    logger.info("创建分享链接: session=%s, share_id=%s", session_id, share_id)
    return {
        "success": True,
        "share_id": share_id,
        "token": token,
        "url": f"/share/{token}",
        "expires_at": expires_at or None,
        "has_password": bool(password),
    }


def get_share_by_token(token: str) -> Optional[dict]:
    """根据分享 token 获取分享信息。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        return None
    return dict(row)


def validate_share_access(share: dict, password: str = "") -> dict:
    """
    验证分享链接的访问权限。

    Returns:
        {"valid": True} 或 {"valid": False, "reason": "..."}
    """
    # 检查过期
    if share.get("expires_at"):
        try:
            expires = datetime.datetime.fromisoformat(share["expires_at"])
            if datetime.datetime.now() > expires:
                return {"valid": False, "reason": "链接已过期"}
        except ValueError:
            pass

    # 检查密码
    if share.get("password"):
        if not password:
            return {"valid": False, "reason": "需要密码", "need_password": True}
        if password != share["password"]:
            return {"valid": False, "reason": "密码错误"}

    return {"valid": True}


def get_shared_session_data(share: dict) -> Optional[dict]:
    """
    获取分享的会话数据（只读）。
    包含会话信息和消息列表。
    """
    session_id = share["session_id"]

    with get_db() as conn:
        session = conn.execute(
            "SELECT id, title, status, mode, created_at FROM chat_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not session:
            return None

        messages = conn.execute(
            "SELECT id, role, content, msg_type, metadata, created_at "
            "FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()

        # 更新浏览次数
        conn.execute(
            "UPDATE share_links SET view_count = view_count + 1 WHERE id = ?",
            (share["id"],),
        )

    return {
        "session": dict(session),
        "messages": [dict(m) for m in messages],
    }


def list_share_links(session_id: str) -> list[dict]:
    """列出会话的所有分享链接。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM share_links WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_share_link(share_id: str, user_id: str = "") -> bool:
    """删除分享链接。"""
    with get_db() as conn:
        if user_id:
            deleted = conn.execute(
                "DELETE FROM share_links WHERE id = ? AND user_id = ?",
                (share_id, user_id),
            ).rowcount
        else:
            deleted = conn.execute(
                "DELETE FROM share_links WHERE id = ?", (share_id,)
            ).rowcount
    return deleted > 0
