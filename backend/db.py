from __future__ import annotations

# backend/db.py
import sqlite3
from contextlib import contextmanager
from typing import Iterator
import os
import yaml

# DB 路径解析顺序：
# 1) 环境变量 PORT_DB_PATH（最高优先级）
# 2) config.yaml 的 test_db_path（当检测到测试环境时）
# 3) config.yaml 的 db_path（生产默认）
# 4) 兜底：项目根 portfolio.db；若不存在但 legacy 路径 backend/data/portfolio.db 存在则使用它
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_ROOT_DB = os.path.join(_PROJECT_ROOT, "portfolio.db")
_LEGACY_DB = os.path.join(_PROJECT_ROOT, "backend", "data", "portfolio.db")


def _read_config_yaml() -> dict:
    cfg_path = os.path.join(_PROJECT_ROOT, "config.yaml")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        out = {}
        for k in ("db_path", "test_db_path"):
            v = cfg.get(k)
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()
        return out
    except Exception:
        return {}


def get_db_path(_: str | None = None) -> str:
    env_path = os.environ.get("PORT_DB_PATH")
    cfg = _read_config_yaml()
    cfg_db = cfg.get("db_path")
    cfg_test = cfg.get("test_db_path")
    is_test = (os.environ.get("APP_ENV") == "test") or (os.environ.get("PYTEST_CURRENT_TEST") is not None)

    if env_path:
        path = env_path
    elif is_test and cfg_test:
        path = cfg_test
    elif cfg_db:
        path = cfg_db
    else:
        # Prefer root DB; if missing but legacy exists, use legacy
        path = _ROOT_DB if os.path.exists(_ROOT_DB) or not os.path.exists(_LEGACY_DB) else _LEGACY_DB

    # 确保目录存在
    dirn = os.path.dirname(path) or "."
    os.makedirs(dirn, exist_ok=True)
    return path


@contextmanager
def get_conn(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """
    获取 SQLite 连接。优先使用显式传入的 db_path，否则走 get_db_path()。
    打开 foreign_keys，设置 row_factory 为 Row。
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
        isolation_level=None,
    )
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()
