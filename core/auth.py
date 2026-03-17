"""
用户认证模块
===========
JWT Token 认证：注册、登录、Token 签发与验证。
密码使用 PBKDF2-SHA256 加盐哈希存储。
"""

import os
import uuid
import hmac
import json
import time
import hashlib
import logging
import datetime
import base64
from typing import Optional

from .db import get_db

logger = logging.getLogger("agent_skills.auth")

# JWT 密钥：优先从环境变量读取，否则自动生成（重启后旧 token 失效）
JWT_SECRET = os.environ.get("JWT_SECRET", uuid.uuid4().hex)
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))


# ── 密码哈希 ──────────────────────────────────────

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """PBKDF2-SHA256 哈希密码，返回 (hash_hex, salt_hex)。"""
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hashed.hex(), salt


def _verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    """验证密码是否匹配。"""
    computed, _ = _hash_password(password, salt_hex)
    return hmac.compare_digest(computed, hash_hex)


# ── JWT Token ────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(user_id: str, username: str) -> str:
    """签发 JWT Token。"""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload_data = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + JWT_EXPIRE_HOURS * 3600,
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())
    signature_input = f"{header}.{payload}".encode()
    signature = _b64url_encode(
        hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def verify_token(token: str) -> Optional[dict]:
    """
    验证 JWT Token，返回 payload 字典。
    失败返回 None。
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, signature = parts

        # 验证签名
        expected_sig = _b64url_encode(
            hmac.new(
                JWT_SECRET.encode(),
                f"{header}.{payload}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # 解析 payload
        payload_data = json.loads(_b64url_decode(payload))

        # 检查过期
        if payload_data.get("exp", 0) < int(time.time()):
            return None

        return payload_data
    except Exception as exc:
        logger.debug("Token 验证失败: %s", exc)
        return None


# ── 用户管理 ──────────────────────────────────────

def register_user(username: str, password: str) -> dict:
    """
    注册新用户。

    Returns:
        {"success": True, "user_id": "...", "token": "..."} 或
        {"success": False, "message": "错误原因"}
    """
    username = username.strip()
    if not username or len(username) < 2 or len(username) > 30:
        return {"success": False, "message": "用户名长度需在 2-30 之间"}
    if not password or len(password) < 6:
        return {"success": False, "message": "密码长度至少 6 位"}

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return {"success": False, "message": "用户名已存在"}

        user_id = uuid.uuid4().hex[:12]
        hash_hex, salt_hex = _hash_password(password)
        now = datetime.datetime.now().isoformat()

        conn.execute(
            "INSERT INTO users (id, username, password_hash, password_salt, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, hash_hex, salt_hex, now),
        )

    token = create_token(user_id, username)
    logger.info("用户注册成功: %s (%s)", username, user_id)
    return {"success": True, "user_id": user_id, "username": username, "token": token}


def login_user(username: str, password: str) -> dict:
    """
    用户登录。

    Returns:
        {"success": True, "user_id": "...", "token": "..."} 或
        {"success": False, "message": "错误原因"}
    """
    username = username.strip()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, password_salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row:
        return {"success": False, "message": "用户名或密码错误"}

    if not _verify_password(password, row["password_hash"], row["password_salt"]):
        return {"success": False, "message": "用户名或密码错误"}

    token = create_token(row["id"], row["username"])
    logger.info("用户登录成功: %s (%s)", row["username"], row["id"])
    return {"success": True, "user_id": row["id"], "username": row["username"], "token": token}


def get_user_from_request(request) -> Optional[dict]:
    """
    从请求中提取并验证用户信息。
    支持 Authorization: Bearer <token> 头。

    Returns:
        {"user_id": "...", "username": "..."} 或 None
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    payload = verify_token(token)
    if not payload:
        return None
    return {"user_id": payload["sub"], "username": payload["username"]}
