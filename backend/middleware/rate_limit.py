"""滑动窗口限流中间件 —— 基于 IP，纯内存实现（零外部依赖）。"""
import os
import time
from collections import defaultdict
from fastapi import Request, HTTPException

# 配置
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))     # 窗口秒数
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX", "30"))          # 窗口内最大请求数
BURST_MULTIPLIER = int(os.getenv("RATE_LIMIT_BURST", "3"))     # Chat 端点突发倍数

# 存储: {ip: [(timestamp, ...)]}
_windows: dict[str, list[float]] = defaultdict(list)

# 需要严格限流的端点（走 MAX_REQUESTS）
STRICT_PATHS = {"/chat"}
# 管理端点（走 MAX_REQUESTS * BURST_MULTIPLIER）
ADMIN_PATHS = {"/knowledge", "/cost/summary", "/cost/trend", "/stats/intents"}

# 公开端点不限流
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _get_ip(request: Request) -> str:
    """获取客户端 IP（优先取 X-Forwarded-For）。"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    """滑动窗口限流。"""
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/docs"):
        return await call_next(request)

    ip = _get_ip(request)
    now = time.time()
    window = _windows[ip]

    # 清理过期记录
    cutoff = now - WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.pop(0)

    # 判断限流阈值
    if path in STRICT_PATHS:
        limit = MAX_REQUESTS
    elif any(path.startswith(p) for p in ADMIN_PATHS):
        limit = MAX_REQUESTS * BURST_MULTIPLIER
    else:
        limit = MAX_REQUESTS

    if len(window) >= limit:
        reset_after = WINDOW_SECONDS - (now - window[0])
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请 {int(reset_after)} 秒后重试",
            headers={"Retry-After": str(int(reset_after))},
        )

    window.append(now)
    return await call_next(request)
