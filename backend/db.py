import sqlite3
from contextlib import contextmanager
from typing import Iterator
import os

DEFAULT_CFG_PATH = os.environ.get("PORT_CFG", "config.yaml")

def get_db_path(cfg_path: str = DEFAULT_CFG_PATH) -> str:
    import yaml
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["db_path"]

@contextmanager
def get_conn(cfg_path: str = DEFAULT_CFG_PATH) -> Iterator[sqlite3.Connection]:
    path = get_db_path(cfg_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
