from ..db import get_conn
from ..logs import LogContext
from .config_svc import get_config
from ..domain.txn_engine import compute_position_after_trade, compute_cash_mirror, round_price, round_quantity, round_shares, round_amount
from ..repository import txn_repo, position_repo, instrument_repo
from typing import List, Tuple, Dict

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

def list_txn(page:int, size:int) -> Tuple[int, List[dict]]:
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
        name_map: Dict[str, str] = instrument_repo.name_map_for(conn, codes)

        # 计算每个 SELL 交易的 realized PnL，构建 id->pnl 映射
        pnl_map: Dict[int, float] = {}
        for code in codes:
            # 拉该代码的全历史交易，按时间顺序
            hist = txn_repo.list_txns_for_code_ordered(conn, code)
            pos_shares = 0.0
            avg_cost = 0.0
            for h in hist:
                act = (h["action"] or "").upper()
                sh = float(h["shares"] or 0.0)
                pr = float(h["price"] or 0.0)
                fee = float(h["fee"] or 0.0)
                if act == "BUY":
                    new_shares = pos_shares + abs(sh)
                    total_cost = pos_shares * avg_cost + abs(sh) * pr + fee
                    avg_cost = (total_cost / new_shares) if new_shares > 0 else 0.0
                    pos_shares = new_shares
                elif act == "SELL":
                    qty = abs(sh)
                    pnl = round_amount(qty * (pr - avg_cost) - fee)
                    pnl_map[int(h["id"])] = pnl
                    pos_shares = round_shares(pos_shares + sh)  # sh 为负
                    if pos_shares <= 0.01:  # 调整为2位小数阈值
                        pos_shares = 0.0
                        avg_cost = 0.0
                else:
                    # DIV/FEE/ADJ 不影响均价法持仓成本计算
                    pass

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
            
            # 处理 realized_pnl
            rp = pnl_map.get(int(it["id"]))
            if rp is not None and (it["action"] or "").upper() == "SELL":
                it["realized_pnl"] = float(rp)  # rp 已经通过 _round_financial 处理过
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
        # 1) 写入原始交易（先写入，获取 id，随后设置 group_id=自身 id）
        orig_id = txn_repo.insert_txn(conn, ts_code, date, action, shares, price, data.get("amount"), fee, data.get("notes",""), None)
        txn_repo.update_group_id(conn, orig_id, orig_id)
        # 2) 更新原标的持仓（仅 BUY/SELL）
        row = position_repo.get_position(conn, ts_code)
        old_shares, old_cost = (row["shares"], row["avg_cost"]) if row else (0.0, 0.0)

        if action in ("BUY", "SELL"):
            # Position math delegated to domain engine
            qty_abs = abs(shares)
            new_shares, new_cost = compute_position_after_trade(old_shares, old_cost, action, qty_abs, price, fee)
            if action == "SELL" and new_shares < -1e-6:
                conn.rollback()
                raise ValueError("Sell exceeds current shares")
            position_repo.upsert_position(conn, ts_code, new_shares, new_cost, date)

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
                if amt > 0:
                    c_new_shares = round_shares(cash_old_shares + amt)
                    c_total_cost = round_amount(cash_old_shares * cash_old_cost + amt * 1.0)
                    c_new_cost = round_price((c_total_cost / c_new_shares) if c_new_shares > 0 else 0.0)
                    position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
                else:
                    c_new_shares = round_shares(cash_old_shares - abs(amt))
                    c_new_cost = 0.0 if abs(c_new_shares) < 0.01 else cash_old_cost
                    position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
        elif not is_cash_inst:
            # 现金镜像（由 domain engine 决策）
            mirror_action, mirror_abs_shares = compute_cash_mirror(action, data["shares"], price, fee, data.get("amount"))

            if mirror_action and mirror_abs_shares > 0:
                # 写入现金镜像交易（price=1，fee=0），shares 符号随 action 约定
                mirror_shares = mirror_abs_shares if mirror_action == "BUY" else -mirror_abs_shares
                txn_repo.insert_txn(conn, cash_code, date, mirror_action, mirror_shares, 1.0, None, 0.0,
                                    f"AUTO-MIRROR for {ts_code} {action}", orig_id)
                # 更新现金持仓
                cash_row = position_repo.get_position(conn, cash_code)
                cash_old_shares, cash_old_cost = (cash_row["shares"], cash_row["avg_cost"]) if cash_row else (0.0, 0.0)
                if mirror_action == "BUY":
                    c_new_shares = round_shares(cash_old_shares + mirror_abs_shares)
                    c_total_cost = round_amount(cash_old_shares * cash_old_cost + mirror_abs_shares * 1.0)
                    c_new_cost = round_price((c_total_cost / c_new_shares) if c_new_shares > 0 else 0.0)
                    position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
                else:  # SELL 现金
                    c_new_shares = round_shares(cash_old_shares - mirror_abs_shares)
                    # 允许现金为负代表透支；仅在归零时将均价清 0，其余保留旧均价（通常为 1）
                    c_new_cost = 0.0 if abs(c_new_shares) < 0.01 else cash_old_cost
                    position_repo.upsert_position(conn, cash_code, c_new_shares, c_new_cost, date)
        conn.commit()
        pos = position_repo.get_position(conn, ts_code)
    result = {"ts_code": ts_code, "shares": pos["shares"], "avg_cost": pos["avg_cost"]}
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
