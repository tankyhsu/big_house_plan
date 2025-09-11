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
            "watchlist",
            "operation_log",
        ]

        backup_data = {}
        backup_data["timestamp"] = datetime.now().isoformat()
        backup_data["backup_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        backup_data["version"] = "1.1"  # Updated version to reflect new tables
        backup_data["tables"] = {}
        backup_data["summary"] = {}

        with get_conn() as conn:
            conn.row_factory = lambda cursor, row: dict(
                zip([col[0] for col in cursor.description], row)
            )
            for table in business_tables:
                try:
                    cursor = conn.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    backup_data["tables"][table] = rows
                    backup_data["summary"][table] = len(rows)
                except Exception as e:
                    # Skip tables that don't exist in older schemas
                    print(f"Warning: Could not backup table {table}: {e}")
                    backup_data["summary"][table] = f"Error: {str(e)}"

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

        # Tables to restore in dependency order (foreign key constraints)
        business_tables = [
            "operation_log",  # Independent table, no foreign keys
            "signal",         # Independent table
            "category_daily", # Depends on category
            "portfolio_daily", # Depends on category
            "position",       # Independent table
            "ma_cache",       # Independent table
            "price_eod",      # Independent table
            "txn",           # Independent table
            "watchlist",     # Independent table
            "instrument",    # Depends on category
            "category",      # Referenced by other tables
            "config",        # Independent table
        ]

        with get_conn() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                restored_tables = []
                skipped_tables = []
                
                # Clear existing data in reverse dependency order
                for table in business_tables:
                    if table in backup_data["tables"]:
                        try:
                            conn.execute(f"DELETE FROM {table}")
                            restored_tables.append(table)
                        except Exception as e:
                            print(f"Warning: Could not clear table {table}: {e}")
                            skipped_tables.append(table)

                # Restore data
                for table_name, rows in backup_data["tables"].items():
                    if not rows or table_name in skipped_tables:
                        continue
                    
                    try:
                        columns = list(rows[0].keys())
                        placeholders = ",".join(["?" for _ in columns])
                        insert_sql = (
                            f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                        )
                        for row in rows:
                            values = [row[col] for col in columns]
                            conn.execute(insert_sql, values)
                    except Exception as e:
                        print(f"Warning: Could not restore table {table_name}: {e}")
                        skipped_tables.append(table_name)

                conn.commit()
                
                # Prepare result message
                total_tables = len([t for t in backup_data["tables"] if backup_data["tables"][t]])
                restored_count = len(restored_tables)
                skipped_count = len(skipped_tables)
                
                message = f"数据恢复完成，成功恢复 {restored_count}/{total_tables} 个表"
                if skipped_count > 0:
                    message += f"，跳过 {skipped_count} 个表"
                message += "，建议手动重新计算组合数据"
                
                return {
                    "message": message,
                    "restored_tables": restored_tables,
                    "skipped_tables": skipped_tables,
                    "backup_version": backup_data.get("version", "unknown"),
                }
            except Exception as e:
                conn.rollback()
                raise e
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="备份文件格式错误，无法解析JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

