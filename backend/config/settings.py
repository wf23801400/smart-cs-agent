"""
集中配置 —— 对标 Spring Boot application-{profile}.yml。
通过 APP_ENV 环境变量切换 dev / test / prod。
用法：
    from backend.config import settings
    api_key = settings.DEEPSEEK_API_KEY
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _resolve_env_file() -> str:
    """根据 APP_ENV 解析 .env 文件路径，不存在则 fallback 到 .env。"""
    app_env = os.getenv("APP_ENV", "dev").strip()
    env_file = PROJECT_ROOT / f".env.{app_env}"
    if env_file.exists():
        return str(env_file)
    fallback = PROJECT_ROOT / ".env"
    if fallback.exists():
        return str(fallback)
    return ""


class Settings(BaseSettings):
    """所有配置项集中定义，自动从环境变量 + .env 文件加载。"""

    # ── 环境标识 ───────────────────────────────────
    APP_ENV: str = Field(default="dev", validation_alias="APP_ENV")

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def strip_env(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    # ── LLM API ────────────────────────────────────
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # ── LangSmith（可选） ──────────────────────────
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "smart-cs-agent"

    # ── MySQL ──────────────────────────────────────
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "smart_cs_agent"

    # ── Redis ──────────────────────────────────────
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379

    # ── 限流 ──────────────────────────────────────
    RATE_LIMIT_WINDOW: int = 60
    RATE_LIMIT_MAX: int = 30
    RATE_LIMIT_BURST: int = 3

    # ── API 认证 ───────────────────────────────────
    API_KEY: str = ""  # 支持逗号分隔多个 Key

    @property
    def api_keys(self) -> set[str]:
        """解析为集合。"""
        return {k.strip() for k in self.API_KEY.split(",") if k.strip()}

    # ── 环境感知属性 ──────────────────────────────
    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "dev"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def server_port(self) -> int:
        """各环境默认端口。"""
        return {"dev": 8001, "test": 8002, "prod": 8000}.get(self.APP_ENV, 8000)

    @property
    def reload_enabled(self) -> bool:
        """只有 dev 环境启热重载。"""
        return self.APP_ENV == "dev"

    model_config = {
        "env_file": _resolve_env_file(),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# 全局单例
settings = Settings()
