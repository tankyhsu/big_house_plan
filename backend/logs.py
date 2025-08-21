import json, time, uuid, datetime as dt
from typing import Optional, Tuple, List, Dict, Any
from .db import get_conn

DDL = """
CREATE TABLE IF NOT EXISTS operation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  request_id TEXT,
  before_json TEXT,
  after_json TEXT,
  payload_json TEXT,
  result TEXT,
  err_msg TEXT,
  latency_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_log_ts ON operation_log(ts);
CREATE INDEX IF NOT EXISTS idx_log_action ON operation_log(action);
"""

def ensure_log_schema():
    with get_conn() as conn:
        conn.executescript(DDL)
        conn.commit()

class LogContext:
    def __init__(self, action: str, user: str = "owner"):
        self.action = action
        self.user = user
        self.request_id = str(uuid.uuid4())
        self.start = time.perf_counter()
        self.before = None
        self.after = None
        self.payload = None
        self.entity_type = None
        self.entity_id = None

    def set_entity(self, etype: str, eid: str):
        self.entity_type = etype
        self.entity_id = eid

    def set_before(self, obj): self.before = obj
    def set_after(self, obj): self.after = obj
    def set_payload(self, obj): self.payload = obj

    def write(self, result: str = "OK", err: Optional[str] = None):
        elapsed_ms = int((time.perf_counter() - self.start) * 1000)
        rec = {
            "ts": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
            "user": self.user,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "request_id": self.request_id,
            "before_json": json.dumps(self.before, ensure_ascii=False) if self.before is not None else None,
            "after_json": json.dumps(self.after, ensure_ascii=False) if self.after is not None else None,
            "payload_json": json.dumps(self.payload, ensure_ascii=False) if self.payload is not None else None,
            "result": result,
            "err_msg": err,
            "latency_ms": elapsed_ms,
        }
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO operation_log
                (ts,user,action,entity_type,entity_id,request_id,before_json,after_json,payload_json,result,err_msg,latency_ms)
                VALUES(:ts,:user,:action,:entity_type,:entity_id,:request_id,:before_json,:after_json,:payload_json,:result,:err_msg,:latency_ms)""",
                rec
            )
            conn.commit()

def search_logs(q: str|None, action: str|None, ts_from: str|None, ts_to: str|None, page:int, size:int):
    where = []
    params = {}
    if q:
        where.append("(payload_json LIKE :q OR before_json LIKE :q OR after_json LIKE :q)")
        params["q"] = f"%{q}%"
    if action:
        where.append("action = :action")
        params["action"] = action
    if ts_from:
        where.append("ts >= :from")
        params["from"] = ts_from
    if ts_to:
        where.append("ts <= :to")
        params["to"] = ts_to
    wh = " WHERE " + " AND ".join(where) if where else ""
    sql = f"SELECT * FROM operation_log{wh} ORDER BY ts DESC LIMIT :limit OFFSET :offset"
    count_sql = f"SELECT COUNT(1) AS cnt FROM operation_log{wh}"
    with get_conn() as conn:
        total = conn.execute(count_sql, params).fetchone()["cnt"]
        rows = conn.execute(sql, {**params, "limit": size, "offset": (page-1)*size}).fetchall()
        return total, [dict(r) for r in rows]
