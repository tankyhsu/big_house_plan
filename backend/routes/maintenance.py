from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response

from ..db import get_conn

router = APIRouter()


@router.post("/api/backup")
def api_backup():
    try:
        import json
        from datetime import datetime

        business_tables = [
            "config",
            "category",
            "instrument",
            "txn",
            "price_eod",
            "ma_cache",
            "position",
            "portfolio_daily",
            "category_daily",
            "signal",
        ]

        backup_data = {}
        backup_data["timestamp"] = datetime.now().isoformat()
        backup_data["backup_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        backup_data["version"] = "1.0"
        backup_data["tables"] = {}
        backup_data["summary"] = {}

        with get_conn() as conn:
            conn.row_factory = lambda cursor, row: dict(
                zip([col[0] for col in cursor.description], row)
            )
            for table in business_tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                backup_data["tables"][table] = rows
                backup_data["summary"][table] = len(rows)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M")
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"portfolio_backup_{date_str}_{time_str}_{timestamp}.json"

        return Response(
            content=json.dumps(backup_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.post("/api/restore")
async def api_restore(file: UploadFile = File(...)):
    try:
        import json

        if not file.filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="只支持JSON备份文件")

        content = await file.read()
        backup_data = json.loads(content.decode("utf-8"))

        if "tables" not in backup_data:
            raise HTTPException(status_code=400, detail="备份文件格式不正确")

        with get_conn() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                business_tables = [
                    "signal",
                    "category_daily",
                    "portfolio_daily",
                    "position",
                    "ma_cache",
                    "price_eod",
                    "txn",
                    "instrument",
                    "category",
                    "config",
                ]

                for table in business_tables:
                    if table in backup_data["tables"]:
                        conn.execute(f"DELETE FROM {table}")

                for table_name, rows in backup_data["tables"].items():
                    if not rows:
                        continue
                    columns = list(rows[0].keys())
                    placeholders = ",".join(["?" for _ in columns])
                    insert_sql = (
                        f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                    )
                    for row in rows:
                        values = [row[col] for col in columns]
                        conn.execute(insert_sql, values)

                conn.commit()
                return {
                    "message": f"数据恢复成功，共恢复 {len(backup_data['tables'])} 个表，建议手动重新计算组合数据",
                }
            except Exception as e:
                conn.rollback()
                raise e
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="备份文件格式错误，无法解析JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

