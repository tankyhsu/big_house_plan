from __future__ import annotations

from ..db import get_conn
from ..logs import LogContext
from .config_svc import get_config
from ..domain.txn_engine import compute_position_after_trade, compute_cash_mirror, compute_position_with_corporate_actions, round_price, round_quantity, round_shares, round_amount
from ..repository import txn_repo, position_repo, instrument_repo

def _ensure_txn_group_id():
    """确保 txn 表存在 group_id 列（用于将原始与现金镜像交易分组）。"""
    try:
        with get_conn() as conn:
            cols = conn.execute("PRAGMA table_info(txn)").fetchall()
            names = {c[1] for c in cols}
            if "group_id" not in names:
                conn.execute("ALTER TABLE txn ADD COLUMN group_id INTEGER")
                conn.commit()
    except Exception:
        # 容错：不因迁移失败而阻断主流程（第一次运行可能并发等），
        # 下次调用会再次尝试。
        pass

def list_txn(page:int, size:int) -> tuple[int, list[dict]]:
    """分页查询交易流水，并补充：
    - name: instrument.name
    - realized_pnl: 仅 SELL 行计算 = qty * (price - avg_cost_at_that_time) - fee
      通过对该 ts_code 的全历史交易按时间顺序重放来获得 SELL 当时的成本。
    """
    _ensure_txn_group_id()
    with get_conn() as conn:
        total = txn_repo.count_all(conn)
        cur_rows = txn_repo.list_txn_page(conn, page, size)
        items = [dict(r) for r in cur_rows]

        if not items:
            return total, items

        # 准备名称映射
        codes = sorted(list({r["ts_code"] for r in items}))
        name_map: dict[str, str] = instrument_repo.name_map_for(conn, codes)

        # realized_pnl 现在存储在数据库中，无需重新计算

        # 组装输出，统一处理浮点数精度
        for it in items:
            it["name"] = name_map.get(it["ts_code"])  # 可能为 None
            
            # 格式化数字字段的精度
            if it.get("shares") is not None:
                it["shares"] = round_shares(float(it["shares"]))
            if it.get("price") is not None:
                it["price"] = round_price(float(it["price"]))
            if it.get("amount") is not None and it["amount"] is not None:
                it["amount"] = round_amount(float(it["amount"]))
            if it.get("fee") is not None:
                it["fee"] = round_amount(float(it["fee"]))
            
            # 处理 realized_pnl（现在直接来自数据库）
            if it.get("realized_pnl") is not None:
                it["realized_pnl"] = round_amount(float(it["realized_pnl"]))
            else:
                it["realized_pnl"] = None

        return total, items

def create_txn(data: dict, log: LogContext) -> dict:
    _ensure_txn_group_id()
    action = data["action"].upper()
    shares = float(data["shares"])
    fee = float(data.get("fee") or 0)
    price = float(data.get("price") or 0)
    date = data["date"]  # YYYY-MM-DD
    ts_code = data["ts_code"]
    if action == "SELL":
        shares = -abs(shares)
    elif action in ("BUY","DIV","FEE","ADJ"):
        shares = abs(shares)
    else:
        raise ValueError("Unsupported action")

    with get_conn() as conn:
        # 1) 获取当前持仓信息（用于计算realized_pnl）
        row = position_repo.get_position(conn, ts_code)
        old_shares, old_cost = (row["shares"], row["avg_cost"]) if row else (0.0, 0.0)
        
        # 2) 计算realized_pnl（仅对SELL交易）
        realized_pnl = None
        if action == "SELL":
            qty_abs = abs(shares)
            if old_cost is not None and price is not None:
                from ..domain.txn_engine import round_amount
                realized_pnl = round_amount(qty_abs * (price - old_cost) - fee)
        
        # 3) 写入原始交易（包含realized_pnl）
        orig_id = txn_repo.insert_txn(conn, ts_code, date, action, shares, price, data.get("amount"), fee, data.get("notes",""), None, realized_pnl)
        txn_repo.update_group_id(conn, orig_id, orig_id)

        # 4) 更新原标的持仓（仅 BUY/SELL）
        if action in ("BUY", "SELL"):
            # Position math delegated to domain engine - now returns realized P&L
            qty_abs = abs(shares)
            new_shares, new_cost, realized_pnl = compute_position_after_trade(old_shares, old_cost, action, qty_abs, price, fee)
            if action == "SELL" and new_shares < -1e-6:
                conn.rollback()
                raise ValueError("Sell exceeds current shares")
            position_repo.upsert_position(conn, ts_code, new_shares, new_cost, date)
            
            # 如果卖出后持仓变为0，自动加入自选关注
            if action == "SELL" and abs(new_shares) <= 1e-6 and old_shares > 0:
                from ..repository import watchlist_repo
                if not watchlist_repo.exists(conn, ts_code):
                    try:
                        watchlist_repo.add(conn, ts_code, "自动从零持仓移入")
                    except Exception:
                        # 忽略添加失败的情况（比如instrument不存在）
                        pass

        # 3) 现金镜像 / 现金直接调整
        cfg = get_config()
        cash_code = str(cfg.get("cash_ts_code") or "CASH.CNY")
        # 查询当前标的类型，若为 CASH 则不做镜像
        inst_type = (instrument_repo.get_type(conn, ts_code) or "").upper()
        is_cash_inst = (inst_type == "CASH") or (ts_code == cash_code)
        if is_cash_inst and action == "ADJ":
            # 直接调整现金头寸：amount>0 视为现金 BUY；amount<0 视为现金 SELL
            amt_field = data.get("amount")
            # 兼容：若前端未提供 amount，则尝试 shares*price；再退化为 shares
            amt = float(amt_field) if amt_field is not None else (abs(float(data.get("shares") or 0.0)) * float(data.get("price") or 0.0))
            if amt == 0:
                amt = abs(float(data.get("shares") or 0.0))
            if abs(amt) > 0:
                cash_row = position_repo.get_position(conn, cash_code)
                cash_old_shares, cash_old_cost = (cash_row["shares"], cash_row["avg_cost"]) if cash_row else (0.0, 0.0)
                # 使用 txn_engine 标准逻辑：amt>0 视为 BUY，amt<0 视为 SELL
                cash_action = "BUY" if amt > 0 else "SELL"
                c_new_shares, c_new_cost, _ = compute_position_after_trade(
                    cash_old_shares, cash_old_cost, cash_action, abs(amt), 1.0, 0.0
                )
                position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
        elif not is_cash_inst:
            # 现金镜像（由 domain engine 决策）
            mirror_action, mirror_abs_shares = compute_cash_mirror(action, data["shares"], price, fee, data.get("amount"))

            if mirror_action and mirror_abs_shares > 0:
                # 写入现金镜像交易（统一使用ADJ类型，price=1，fee=0）
                # shares 符号：正数表示增加现金，负数表示减少现金
                mirror_shares = mirror_abs_shares if mirror_action == "BUY" else -mirror_abs_shares
                txn_repo.insert_txn(conn, cash_code, date, "ADJ", mirror_shares, 1.0, None, 0.0,
                                    f"AUTO-MIRROR for {ts_code} {action}", orig_id, None)
                # 更新现金持仓
                cash_row = position_repo.get_position(conn, cash_code)
                cash_old_shares, cash_old_cost = (cash_row["shares"], cash_row["avg_cost"]) if cash_row else (0.0, 0.0)
                c_new_shares, c_new_cost, _ = compute_position_after_trade(
                    cash_old_shares, cash_old_cost, mirror_action, mirror_abs_shares, 1.0, 0.0
                )
                position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
        conn.commit()
        pos = position_repo.get_position(conn, ts_code)
    
    result = {
        "ts_code": ts_code, 
        "shares": pos["shares"], 
        "avg_cost": pos["avg_cost"],
        "realized_pnl": realized_pnl  # 新增实现盈亏返回值
    }
    log.set_entity("TXN", f"{orig_id}")
    log.set_after({"position": result})
    return result

def bulk_txn(rows: list[dict], log: LogContext) -> dict:
    """批量写入交易（通常用于把历史BUY一次性导入作为建仓记录）"""
    ok, fail = 0, 0
    errs = []
    for i, r in enumerate(rows):
        try:
            # 复用已有 create_txn 逻辑（含均价法/卖出校验）
            create_txn(r, log)
            ok += 1
        except Exception as e:
            fail += 1
            errs.append({"index": i, "ts_code": r.get("ts_code"), "error": str(e)})
    log.set_after({"ok": ok, "fail": fail})
    return {"ok": ok, "fail": fail, "errors": errs}

def get_monthly_pnl_stats() -> list[dict]:
    """按月统计交易收益情况，直接使用txn表中的realized_pnl数据，仅统计SELL操作
    返回格式：
    [
        {
            "month": "2025-01", 
            "total_pnl": 1234.56,  # 总收益
            "profit": 2000.00,     # 盈利
            "loss": -765.44,       # 亏损
            "trade_count": 15,
            "profit_count": 10,
            "loss_count": 5
        },
        ...
    ]
    """
    _ensure_txn_group_id()
    with get_conn() as conn:
        # 通过repository层获取数据
        transactions = txn_repo.get_monthly_realized_pnl(conn)
        
        if not transactions:
            return []
        
        # 按月份统计
        monthly_stats = {}
        
        for txn in transactions:
            trade_date = txn[0]  # YYYY-MM-DD format
            realized_pnl = float(txn[1])
            
            # 提取月份
            month = trade_date[:7]  # YYYY-MM
            
            if month not in monthly_stats:
                monthly_stats[month] = {
                    "month": month,
                    "total_pnl": 0.0,
                    "profit": 0.0,
                    "loss": 0.0,
                    "trade_count": 0,
                    "profit_count": 0,
                    "loss_count": 0
                }
            
            stats = monthly_stats[month]
            stats["total_pnl"] += realized_pnl
            stats["trade_count"] += 1
            
            if realized_pnl > 0:
                stats["profit"] += realized_pnl
                stats["profit_count"] += 1
            elif realized_pnl < 0:
                stats["loss"] += realized_pnl
                stats["loss_count"] += 1
        
        # 转换为列表并按月份倒序排列（最新月份在前）
        result = list(monthly_stats.values())
        result.sort(key=lambda x: x["month"], reverse=True)
        
        # 处理精度
        for stats in result:
            stats["total_pnl"] = round_amount(stats["total_pnl"])
            stats["profit"] = round_amount(stats["profit"])
            stats["loss"] = round_amount(stats["loss"])
        
        return result
