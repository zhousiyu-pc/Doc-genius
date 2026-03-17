"""
API 限流中间件
=============
基于内存的令牌桶限流，按 IP 地址区分。

- 普通 API 请求：每分钟 30 次
- LLM 对话请求（/api/chat/sessions/{id}/messages）：每分钟 5 次
- /api/health 不限流

超限返回 429:
    {"success": false, "error": "rate_limited", "message": "请求过于频繁，请稍后重试"}
"""

import time
import threading
import logging
import re
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("agent_skills.rate_limiter")

# ── 限流配置 ──────────────────────────────────────

# 普通 API：每分钟 30 次
DEFAULT_RATE_LIMIT = 30
DEFAULT_WINDOW_SECONDS = 60

# LLM 对话：每分钟 5 次
LLM_RATE_LIMIT = 5
LLM_WINDOW_SECONDS = 60

# LLM 路径匹配模式：/api/chat/sessions/{id}/messages
_LLM_PATH_PATTERN = re.compile(r"^/api/chat/sessions/[^/]+/messages$")

# 不限流的路径
_EXEMPT_PATHS = {"/api/health"}

# 过期桶清理间隔（秒）
_CLEANUP_INTERVAL = 300  # 5 分钟


class TokenBucket:
    """
    简单的令牌桶实现。

    每个桶以 (max_tokens / window) 的速率补充令牌，
    最多持有 max_tokens 个令牌。消费一个令牌即放行一个请求。
    """

    __slots__ = ("max_tokens", "refill_rate", "tokens", "last_refill")

    def __init__(self, max_tokens: int, window_seconds: int):
        self.max_tokens = max_tokens
        self.refill_rate = max_tokens / window_seconds  # 每秒补充量
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """尝试消费一个令牌。成功返回 True，桶空返回 False。"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    @property
    def is_stale(self) -> bool:
        """桶是否已满且长时间未使用（可以清理）。"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        return elapsed > _CLEANUP_INTERVAL and self.tokens >= self.max_tokens - 1


class RateLimiterStore:
    """
    线程安全的限流桶存储。

    为每个 (ip, bucket_type) 维护一个独立的令牌桶。
    定期清理不活跃的桶以避免内存泄漏。
    """

    def __init__(self):
        self._lock = threading.Lock()
        # key: (ip, bucket_type) -> TokenBucket
        self._buckets: Dict[Tuple[str, str], TokenBucket] = {}
        self._last_cleanup = time.monotonic()

    def is_allowed(self, ip: str, bucket_type: str, max_tokens: int, window_seconds: int) -> bool:
        """
        检查指定 IP 的指定类型桶是否允许请求。

        Args:
            ip: 客户端 IP
            bucket_type: 桶类型标识（"default" 或 "llm"）
            max_tokens: 桶容量
            window_seconds: 时间窗口

        Returns:
            True 表示放行，False 表示限流
        """
        key = (ip, bucket_type)

        with self._lock:
            # 定期清理
            now = time.monotonic()
            if now - self._last_cleanup > _CLEANUP_INTERVAL:
                self._cleanup()
                self._last_cleanup = now

            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(max_tokens, window_seconds)
                self._buckets[key] = bucket

            return bucket.consume()

    def _cleanup(self):
        """清理不活跃的桶（已在锁内调用）。"""
        stale_keys = [k for k, v in self._buckets.items() if v.is_stale]
        for k in stale_keys:
            del self._buckets[k]
        if stale_keys:
            logger.debug("清理了 %d 个不活跃的限流桶", len(stale_keys))


# 全局存储实例
_store = RateLimiterStore()


def _get_client_ip(request: Request) -> str:
    """
    从请求中提取客户端 IP。
    优先读取 X-Forwarded-For / X-Real-IP（反向代理场景）。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 取第一个（最原始的客户端 IP）
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # 回退到直连 IP
    if request.client:
        return request.client.host

    return "unknown"


def _is_llm_path(path: str) -> bool:
    """判断路径是否为 LLM 对话请求。"""
    return bool(_LLM_PATH_PATTERN.match(path))


def _is_exempt(path: str) -> bool:
    """判断路径是否免于限流。"""
    return path in _EXEMPT_PATHS


_RATE_LIMIT_RESPONSE = JSONResponse(
    {
        "success": False,
        "error": "rate_limited",
        "message": "请求过于频繁，请稍后重试",
    },
    status_code=429,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette 限流中间件。

    - /api/health：不限流
    - /api/chat/sessions/{id}/messages：LLM 限流（5次/分钟）
    - 其他 /api/ 路径：默认限流（30次/分钟）
    - 非 /api/ 路径（静态资源等）：不限流
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 非 API 路径或豁免路径，直接放行
        if not path.startswith("/api/") or _is_exempt(path):
            return await call_next(request)

        client_ip = _get_client_ip(request)

        # LLM 路径走更严格的限流
        if _is_llm_path(path):
            if not _store.is_allowed(client_ip, "llm", LLM_RATE_LIMIT, LLM_WINDOW_SECONDS):
                logger.warning("LLM 限流触发: ip=%s, path=%s", client_ip, path)
                return JSONResponse(
                    {
                        "success": False,
                        "error": "rate_limited",
                        "message": "请求过于频繁，请稍后重试",
                    },
                    status_code=429,
                )

        # 所有 API 路径走默认限流
        if not _store.is_allowed(client_ip, "default", DEFAULT_RATE_LIMIT, DEFAULT_WINDOW_SECONDS):
            logger.warning("API 限流触发: ip=%s, path=%s", client_ip, path)
            return JSONResponse(
                {
                    "success": False,
                    "error": "rate_limited",
                    "message": "请求过于频繁，请稍后重试",
                },
                status_code=429,
            )

        return await call_next(request)
