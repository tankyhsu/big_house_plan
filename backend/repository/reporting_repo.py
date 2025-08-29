from sqlite3 import Connection


def active_instruments_with_pos_and_price(conn: Connection, date_dash: str):
    """
    Return rows of active instruments joined with current position and last close on/before date.
    Columns: ts_code, category_id, shares, avg_cost, eod_close
    """
    return conn.execute(
        """
        SELECT i.ts_code, i.category_id,
               IFNULL(p.shares,0) AS shares,
               IFNULL(p.avg_cost,0) AS avg_cost,
               (SELECT close FROM price_eod pe
                  WHERE pe.ts_code=i.ts_code AND pe.trade_date<=?
                  ORDER BY pe.trade_date DESC LIMIT 1) AS eod_close
        FROM instrument i
        LEFT JOIN position p ON p.ts_code=i.ts_code
        WHERE i.active=1
        """,
        (date_dash,),
    ).fetchall()

