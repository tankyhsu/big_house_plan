# Backend API & Services Overview

This memory summarizes the current backend (FastAPI) API surface, key services, data flow, and related frontend hooks for quick navigation and future changes.

## FastAPI App
- App entry: `backend/api.py` with CORS for Vite ports 5173–5177.
- Startup: `ensure_log_schema()` and `ensure_default_config()`; optional background price sync commented out.
- Health: `GET /health`, Version: `GET /version`.

## Core API Groups

### Dashboard & Series
- `GET /api/dashboard` (query `date=YYYYMMDD`): portfolio summary (market_value, cost, pnl, ret, signal stats, price fallback flag). Uses `dashboard_svc.get_dashboard`.
- `GET /api/dashboard/aggregate` (start/end YYYYMMDD, period=day|week|month): aggregated KPI sequence; uses `dashboard_svc.aggregate_kpi`.
- `GET /api/series/position` (start/end YYYYMMDD, `ts_codes=code1,code2`): time series by instrument from `portfolio_daily` joined with `instrument`.

### Category & Position Views (read)
- `GET /api/category` (date YYYYMMDD): category distribution view via `dashboard_svc.list_category`.
- `GET /api/position` (date YYYYMMDD): per-instrument position view via `dashboard_svc.list_position`.

### Signals
- `GET /api/signal` (date YYYYMMDD, optional `type`, `ts_code`): daily signals via `dashboard_svc.list_signal`.
- `GET /api/signal/all` (optional `type`, `ts_code`, `start_date`, `end_date`, `limit`): historical signals via `dashboard_svc.list_signal_all`.
- `POST /api/signal/create`: manual signal creation supporting scope types (INSTRUMENT/CATEGORY/MULTI_*/ALL_*). Calls `signal_svc.create_manual_signal_extended`.
- `POST /api/signal/rebuild-historical`: clears and regenerates all historical signals. Calls `signal_svc.rebuild_all_historical_signals`.
- `POST /api/signal/rebuild-structure`: rebuilds last 30 days of structure signals. Calls `SignalGenerationService.rebuild_structure_signals_for_period`.
- `GET /api/signals/current-status` (date YYYYMMDD): separates historical event signals and real-time position status using `SignalService` and `PositionStatusService`.
- `GET /api/positions/status` (date, optional `ts_code`): current position status list or single instrument via `PositionStatusService`.

### Settings
- `GET /api/settings/get`: returns config typed values.
- `POST /api/settings/update` with `{ updates: Record<string, any> }`: upserts config keys.

### Instruments & Categories
- `GET /api/category/list`: all categories for dropdowns.
- `GET /api/instrument/list` (optional `q`, `active_only=true`): autocomplete list via `instrument_svc.list_instruments`.
- `GET /api/instrument/get` (`ts_code`): instrument detail with category names.
- `POST /api/instrument/create` (body ts_code/name/category_id/active/type; `recalc_today` query optional): creates/updates mapping; optional same-day recalculation.
- `POST /api/instrument/update` (ts_code, active): toggles active using `repository.instrument_repo.set_active`.
- `POST /api/instrument/edit` (ts_code, name, category_id, active, type): edit base fields via `instrument_svc.edit_instrument`.
- `POST /api/seed/load` (categories_csv, instruments_csv, optional `recalc_today`): loads seeds; optional same-day calc.
- `GET /api/instrument/lookup` (`ts_code`, optional `date=YYYYMMDD`): helper lookups via `TuShareProvider` with type inference and optional price on/before date.

### Transactions (write triggers recalculation)
- `GET /api/txn/list` (page,size): paginated transactions.
- `GET /api/txn/range` (start/end YYYYMMDD, optional comma `ts_codes`): range query joined with instrument names.
- `POST /api/txn/create`: creates BUY/SELL/DIV/FEE/ADJ and triggers `calc()` for the transaction date.
- `POST /api/txn/bulk` with `{ items: TxnCreate[], recalc: "none"|"latest"|"all" }`: batch import; guarded recalculation strategy.

### Positions (opening/base positions; write triggers recalculation downstream via callers)
- `GET /api/position/raw` (frontend uses): returns raw positions for maintenance; implemented in `position_svc.list_positions_raw`.
- `POST /api/position/update` with `{ ts_code, shares?, avg_cost?, date, opening_date? }`: upsert with opening_date support.
- `POST /api/position/delete` with `{ ts_code, recalc_date? }`: deletes one.
- `POST /api/position/cleanup-zero` with optional `recalc_date`: removes zero-share positions.
- IRR: `GET /api/position/irr` and `/api/position/irr/batch` (used by frontend) via `analytics_svc`.

### Prices & Calc
- `POST /api/sync-prices` with `{ date, recalc }`: syncs EOD prices via `pricing_svc.sync_prices_tushare`; optional calc.
- `POST /api/calc` with `{ date }`: triggers recomputation pipeline via `calc_svc.calc`.
- `GET /api/price/last` (`ts_code`, optional `date`): last price as of date.
- `GET /api/price/ohlc` (`ts_code`, `start`, `end` YYYYMMDD): OHLC range used in K-line charts.

### Backup/Restore
- `POST /api/backup`: dumps business tables as JSON (excludes logs). Returns downloadable JSON with summary and timestamped filename.
- `POST /api/restore` (multipart file): transactional restore of business tables; advises recalculation after restore.

## Key Services & Utilities
- `services/config_svc.py`: defaults, typed `get_config()`, `update_config()`, and `ensure_default_config()` on startup. Includes `cash_ts_code` and `tushare_fund_rate_per_min`.
- `services/position_svc.py`: CRUD-like operations for base positions via `repository.position_repo`.
- `services/dashboard_svc.py`: aggregates views for dashboard/category/position/signal.
- `services/signal_svc.py`: automatic and manual signal creation; structure signal rebuilders.
- `services/pricing_svc.py` + `providers/tushare_provider.py`: external price sync; supports stock/ETF/fund with rate limiting config.
- `services/calc_svc.py`: recomputation pipeline; writes `portfolio_daily`, `category_daily`, signals; dedup rules noted in `schema.sql`.
- `services/analytics_svc.py`: IRR/XIRR for instruments and batch.
- `services/position_status_svc.py`: real-time thresholds (stop gain/loss) and counts for alerts.
- `services/txn_svc.py`: transaction persistence and side-effects.
- `services/utils.py`: date helpers like `yyyyMMdd_to_dash` and rounding utilities via `domain/txn_engine`.

## Data Model (SQLite)
- See `schema.sql` for tables: `config`, `category`, `instrument`, `txn`, `price_eod`, `ma_cache`, `position`, `portfolio_daily`, `category_daily`, `signal`, `operation_log` with supporting indexes.
- Signals table stores historical signals; calc inserters dedup by date + type + scope.

## DB Path Resolution
- `backend/db.py#get_db_path`: priority order
  1) env `PORT_DB_PATH`
  2) `config.yaml.test_db_path` if test (`APP_ENV=test` or under pytest)
  3) `config.yaml.db_path`
  4) fallback to project root `portfolio.db`, else legacy `backend/data/portfolio.db` if exists
- Ensures parent directories exist; `get_conn()` sets `foreign_keys=ON` and `row_factory=Row`.

## Logging
- `backend/logs.py`: `operation_log` table + `LogContext` for structured audit logging with before/after/payload and latency.
- `ensure_log_schema()` creates indices for `ts` and `action`.

## Frontend Integration (selected)
- Axios client base: `VITE_API_BASE` or `http://127.0.0.1:8000` (`frontend/src/api/client.ts`).
- Hooks map closely to endpoints: dashboard/category/position/signals/txn/instrument/price/irr/settings/backup-restore (`frontend/src/api/hooks.ts`).
- UI pages: `src/pages` include Dashboard, Signals, Review, Txn, Settings, PositionEditor, InstrumentDetail.
- Charts: `src/components/charts/*` consume OHLC and position series; `fetchKlineConfig` derives threshold lines from `/api/positions/status`.

## Dev & Ops Notes
- Start both: `bash scripts/dev.sh`; fast start: `bash scripts/dev-fast.sh`.
- Manual: backend `uvicorn backend.api:app --reload --port 8000`; frontend `cd frontend && npm run dev`.
- Config file: `config.yaml` with `db_path`, optional `test_db_path`, `tushare_token` etc. Do not commit secrets.
- Seeds: `seeds/categories.csv`, `seeds/instruments.csv`; DB schema: `schema.sql`.
- Tests present under `backend/tests/` targeting services and API contracts (pytest).

## Conventions & Behaviors
- All write operations (instrument/txn/position edits, seed load, price sync) typically trigger `calc()` for affected date(s).
- Frontend expects dates in `YYYYMMDD` for most queries; server converts to `YYYY-MM-DD` where needed.
- Price fallback logic: when EOD prices missing, some views fallback to avg_cost (flag surfaced in APIs).

## Quick Pointers
- API entry and routing: `backend/api.py`.
- Recalc pipeline: `backend/services/calc_svc.py`.
- Price sync: `backend/services/pricing_svc.py`, provider: `backend/providers/tushare_provider.py`.
- Real-time position status: `backend/services/position_status_svc.py`.
- Backup/restore endpoints at end of `backend/api.py` and matching frontend hooks.
