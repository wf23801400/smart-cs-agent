"""Redis 滑动窗口限流中间件 —— 支持多实例部署，重启不丢"""
import time

import redis
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logger import logger

# ── 从集中配置读取 ──
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
WINDOW_SECONDS = settings.RATE_LIMIT_WINDOW
MAX_REQUESTS = settings.RATE_LIMIT_MAX
BURST_MULTIPLIER = settings.RATE_LIMIT_BURST

STRICT_PATHS = {"/chat"}
ADMIN_PATHS = {"/knowledge", "/cost/summary", "/cost/trend", "/stats/intents"}
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

# ── Redis 连接 ────────────────────────────────────
_r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

logger.bind(component="rate_limit").info(
    f"Redis 限流初始化: {REDIS_HOST}:{REDIS_PORT}"
)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/docs"):
        return await call_next(request)

    ip = _get_ip(request)
    now = time.time()

    # 速率阈值
    if path in STRICT_PATHS:
        limit = MAX_REQUESTS
    elif any(path.startswith(p) for p in ADMIN_PATHS):
        limit = MAX_REQUESTS * BURST_MULTIPLIER
    else:
        limit = MAX_REQUESTS

    # Redis 原子滑动窗口
    window_id = int(now // WINDOW_SECONDS)
    key = f"rate_limit:{ip}:{window_id}"

    try:
        count = _r.incr(key)
        if count == 1:
            _r.expire(key, WINDOW_SECONDS + 5)  # 5 秒冗余防止边界问题

        if count > limit:
            ttl = _r.ttl(key)
            reset_after = ttl if ttl > 0 else WINDOW_SECONDS
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁，请 {int(reset_after)} 秒后重试"},
                headers={"Retry-After": str(int(reset_after))},
            )
    except redis.RedisError as e:
        # Redis 挂了放宽限制，不阻塞业务
        logger.bind(component="rate_limit").warning(f"Redis 不可用，跳过限流: {e}")

    return await call_next(request)
