import os
import sys
import sqlite3
import pytest
from pathlib import Path

# Ensure project root on sys.path
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "portfolio_test.db"
    # Point backend to this temp DB
    os.environ["PORT_DB_PATH"] = str(path)
    # Initialize schema
    schema = Path(_PROJECT_ROOT / "schema.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    return str(path)


@pytest.fixture()
def client(tmp_db_path):
    # Ensure schemas required by logging/config exist before creating client
    from backend.logs import ensure_log_schema
    from backend.services.config_svc import ensure_default_config
    ensure_log_schema()
    ensure_default_config()
    # Import app after DB ready so startup hooks can use it
    from backend.api import app
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db(tmp_db_path):
    # Clean tables before each test for isolation
    # Safety: ensure we only ever wipe the temp DB, never a real one
    assert os.environ.get("PORT_DB_PATH") == tmp_db_path, "Refusing to clean non-temp DB"
    import sqlite3
    tables = [
        "txn",
        "position",
        "instrument",
        "category",
        "price_eod",
        "portfolio_daily",
        "category_daily",
        "signal",
        "config",
    ]
    conn = sqlite3.connect(tmp_db_path)
    try:
        for t in tables:
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    yield
