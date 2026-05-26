"""API Key 认证中间件"""
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logger import logger

_API_KEYS: set[str] = set()
_LOADED = False

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _load_keys():
    global _API_KEYS, _LOADED
    _API_KEYS = settings.api_keys
    logger.bind(component="auth").info(f"已加载 {len(_API_KEYS)} 个 API Key")
    _LOADED = True


async def auth_middleware(request: Request, call_next):
    if not _LOADED:
        _load_keys()

    # 公开端点跳过
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/docs"):
        return await call_next(request)

    # 未配置 API_KEY 时放行（开发模式）
    if not _API_KEYS:
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key not in _API_KEYS:
        return JSONResponse(status_code=401, content={"detail": "无效的 API Key"})

    return await call_next(request)
