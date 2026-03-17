"""
版本管理模块
============
会话的版本快照保存、列表、恢复。
"""

import uuid
import json
import logging
from datetime import datetime, timezone

from core.db import get_db

logger = logging.getLogger("agent_skills.versions")


def save_version(session_id: str, title: str = "") -> dict:
    """
    保存当前会话的版本快照。
    自动递增 version_num，将消息列表 JSON 序列化后存入 snapshot。
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        # 确认会话存在
        session = conn.execute(
            "SELECT id, outline FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 获取当前最大版本号
        row = conn.execute(
            "SELECT MAX(version_num) as max_num FROM session_versions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        next_num = (row["max_num"] or 0) + 1

        # 获取当前会话的所有消息作为快照
        messages = conn.execute(
            "SELECT id, role, content, msg_type, metadata, created_at "
            "FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        snapshot = json.dumps([dict(m) for m in messages], ensure_ascii=False)

        # 自动生成标题
        if not title:
            title = f"v{next_num}"

        vid = uuid.uuid4().hex
        outline = session["outline"] or ""
        conn.execute(
            """INSERT INTO session_versions
               (id, session_id, version_num, title, outline, snapshot, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (vid, session_id, next_num, title, outline, snapshot, now),
        )
        logger.info("保存版本: session=%s version=%d", session_id, next_num)
        return {
            "id": vid,
            "session_id": session_id,
            "version_num": next_num,
            "title": title,
            "outline": outline,
            "created_at": now,
        }


def list_versions(session_id: str) -> list[dict]:
    """列出会话的所有版本（不含 snapshot 大字段）。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, session_id, version_num, title, outline, created_at "
            "FROM session_versions WHERE session_id = ? ORDER BY version_num DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_version(version_id: str) -> dict | None:
    """获取版本详情（含完整消息快照）。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM session_versions WHERE id = ?", (version_id,)
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    # 将 snapshot JSON 字符串解析为列表
    result["snapshot"] = json.loads(result["snapshot"])
    return result


def restore_version(session_id: str, version_id: str) -> bool:
    """
    恢复到指定版本：用快照覆盖当前消息。
    1. 删除当前会话的所有消息
    2. 从版本快照中恢复消息
    3. 恢复会话的 outline
    """
    with get_db() as conn:
        # 获取版本
        ver = conn.execute(
            "SELECT * FROM session_versions WHERE id = ? AND session_id = ?",
            (version_id, session_id),
        ).fetchone()
        if not ver:
            return False

        snapshot = json.loads(ver["snapshot"])

        # 删除当前所有消息
        conn.execute(
            "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
        )

        # 从快照恢复消息
        for msg in snapshot:
            conn.execute(
                """INSERT INTO chat_messages (id, session_id, role, content, msg_type, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg["id"],
                    session_id,
                    msg["role"],
                    msg["content"],
                    msg.get("msg_type", "text"),
                    msg.get("metadata", "{}"),
                    msg["created_at"],
                ),
            )

        # 恢复 outline
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE chat_sessions SET outline = ?, updated_at = ? WHERE id = ?",
            (ver["outline"], now, session_id),
        )

        logger.info("恢复版本: session=%s version=%s", session_id, version_id)
        return True
