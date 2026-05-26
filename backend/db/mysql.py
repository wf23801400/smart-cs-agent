"""MySQL 连接池 (DBUtils.PooledDB)"""
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

from backend.config import settings
from backend.logger import logger

_pool: PooledDB | None = None

POOL_CONFIG = {
    "host": settings.MYSQL_HOST,
    "port": settings.MYSQL_PORT,
    "user": settings.MYSQL_USER,
    "password": settings.MYSQL_PASSWORD,
    "database": settings.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": True,
}

_pool = PooledDB(
    creator=pymysql,
    mincached=5,
    maxconnections=20,
    blocking=True,
    ping=1,
    reset=True,
    **POOL_CONFIG,
)

logger.bind(component="mysql_pool").info(
    "连接池初始化: mincached=5 maxconnections=20"
)


def get_conn() -> pymysql.Connection:
    """从连接池获取 MySQL 连接（调用方必须 conn.close() 归还）"""
    return _pool.connection()


def execute(sql: str, params: tuple = ()) -> tuple:
    """执行 SQL 并返回 (cursor, connection)，调用方负责 conn.close()"""
    conn = _pool.connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur, conn
