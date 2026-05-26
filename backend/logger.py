"""
集中日志管理 — loguru 结构化日志
用法:
    from backend.logger import logger
    logger.bind(session_id="abc", order_id="ORD-001").info("订单查询成功")
"""
import sys
from pathlib import Path

from loguru import logger

# 移除默认 handler
logger.remove()

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 控制台输出（开发用，彩色）
logger.add(
    sys.stderr,
    format="<level>{level: <8}</level> | <cyan>{extra[component]: <16}</cyan> | {message}",
    level="DEBUG",
    colorize=True,
)

# 文件输出（JSON 结构化，给 Loki/ES 用）
logger.add(
    LOG_DIR / "app.json.log",
    format="{time} {level} {message} {extra}",
    level="INFO",
    rotation="50 MB",
    retention="30 days",
    compression="gz",
    serialize=True,  # JSON格式
    backtrace=True,
    diagnose=True,
)

# 错误日志单独一份
logger.add(
    LOG_DIR / "error.json.log",
    format="{time} {level} {message} {extra}",
    level="ERROR",
    rotation="10 MB",
    retention="90 days",
    serialize=True,
    backtrace=True,
    diagnose=True,
)

__all__ = ["logger"]