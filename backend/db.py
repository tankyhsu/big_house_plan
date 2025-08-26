# backend/db.py
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional
import os

# 默认 DB 路径：优先读环境变量 PORT_DB_PATH，否则落到 backend/data/portfolio.db
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "backend", "data", "portfolio.db")
_ENV_DB_PATH = os.environ.get("PORT_DB_PATH")

def get_db_path(_: Optional[str] = None) -> str:
    """
    统一数据库路径来源（不再读取 config.yaml）。
    参数保留仅为向后兼容，传入的值将被忽略。
    优先级：环境变量 PORT_DB_PATH > 默认路径 backend/data/portfolio.db
    """
    path = _ENV_DB_PATH or _DEFAULT_DB_PATH
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

@contextmanager
def get_conn(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """
    获取 SQLite 连接。优先使用显式传入的 db_path，否则走 get_db_path()。
    打开 foreign_keys，设置 row_factory 为 Row。
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,  # 允许在同一进程不同线程使用；如不需要可改回默认
        isolation_level=None      # 使用 autocommit；若你依赖手动事务，可改为默认
    )
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        # 如需提升并发读写，可视情况开启 WAL：
        # conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()