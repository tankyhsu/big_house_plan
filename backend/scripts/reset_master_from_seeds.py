"""
Reset master data (category + instrument) from seeds CSV.

WARNING: This will DELETE all rows in `instrument` and `category` tables,
then re-create from the provided CSVs. It will not touch txn/position tables.

Usage:
  python -m backend.scripts.reset_master_from_seeds \
      --categories seeds/categories.csv \
      --instruments seeds/instruments.csv
"""
from __future__ import annotations

import argparse
from backend.db import get_conn
from backend.logs import LogContext
from backend.services.instrument_svc import seed_load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", required=True)
    ap.add_argument("--instruments", required=True)
    args = ap.parse_args()

    # destructive reset
    with get_conn() as conn:
        conn.execute("DELETE FROM instrument")
        conn.execute("DELETE FROM category")
        conn.commit()

    log = LogContext("RESET_MASTER_FROM_SEEDS")
    res = seed_load(args.categories, args.instruments, log)
    log.write("OK")
    print({"message": "ok", **res})


if __name__ == "__main__":
    main()

