"""API Key 认证中间件"""
import os
from fastapi import Request, HTTPException

# 从环境变量加载，支持多个 Key（逗号分隔）
_API_KEYS: set[str] = set()
_RELOADED = False


def _load_keys():
    global _API_KEYS, _RELOADED
    raw = os.getenv("API_KEY", "")
    _API_KEYS = {k.strip() for k in raw.split(",") if k.strip()}
    _RELOADED = True


def get_api_keys() -> set[str]:
    global _RELOADED
    if not _RELOADED:
        _load_keys()
    return _API_KEYS


# 公开端点，不需要认证
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def auth_middleware(request: Request, call_next):
    """验证 X-API-Key 请求头。"""
    # 公开端点跳过
    if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)

    keys = get_api_keys()
    if not keys:
        # 未配置 API_KEY 时放行（开发模式）
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key not in keys:
        raise HTTPException(status_code=401, detail="无效的 API Key")

    return await call_next(request)
