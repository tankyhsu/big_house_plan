# Backend API & Services Overview

This memory summarizes the current modular backend (FastAPI) API architecture, organized into separate route modules for better maintainability.

## FastAPI App Structure
- **App entry**: `backend/api.py` - Clean entry point with CORS for Vite ports 5173–5177
- **Startup**: `ensure_log_schema()`, `ensure_default_config()`, and `ensure_watchlist_schema()` on startup
- **Modular routing**: All endpoints organized into domain-specific route modules under `backend/routes/`

## Route Modules Architecture

### Base Routes (`backend/routes/base.py`)
- `GET /health`: Health check endpoint
- `GET /version`: Application version endpoint

### Dashboard Routes (`backend/routes/dashboard.py`)  
- `GET /api/dashboard` (query `date=YYYYMMDD`): portfolio summary (market_value, cost, pnl, ret, signal stats, price fallback flag)
- `GET /api/dashboard/aggregate` (start/end YYYYMMDD, period=day|week|month): aggregated KPI sequence
- `GET /api/category` (date YYYYMMDD): category distribution view
- `GET /api/position` (date YYYYMMDD): per-instrument position view
- `GET /api/signal` (date YYYYMMDD, optional `type`, `ts_code`): daily signals
- `GET /api/signal/all` (optional `type`, `ts_code`, `start_date`, `end_date`, `limit`): historical signals
- `GET /api/series/position` (start/end YYYYMMDD, `ts_codes=code1,code2`): time series by instrument

### Signal Routes (`backend/routes/signals.py`)
- `GET /api/signals/current-status` (date YYYYMMDD): separates historical event signals and real-time position status
- `GET /api/positions/status` (date, optional `ts_code`): current position status list or single instrument
- `POST /api/signal/create`: manual signal creation supporting scope types (INSTRUMENT/CATEGORY/MULTI_*/ALL_*)
- `POST /api/signal/rebuild-historical`: clears and regenerates all historical signals
- `POST /api/signal/rebuild-structure`: rebuilds last 30 days of structure signals
- `GET /api/zig/signal/test`: ZIG signal detection testing endpoint
- `POST /api/zig/signal/validate`: ZIG signal validation endpoint

### Watchlist Routes (`backend/routes/watchlist.py`)
- `GET /api/watchlist` (optional date YYYYMMDD): watchlist items with last price
- `POST /api/watchlist/add`: add instrument to watchlist with optional note
- `POST /api/watchlist/remove`: remove instrument from watchlist

### Transaction Routes (`backend/routes/transactions.py`)
- `GET /api/txn/list` (page, size): paginated transaction list
- `GET /api/txn/range` (start/end YYYYMMDD, optional comma `ts_codes`): range query with instrument names
- `POST /api/txn/create`: creates BUY/SELL/DIV/FEE/ADJ and triggers recalculation
- `POST /api/txn/bulk` with `{ items: TxnCreate[], recalc: "none"|"latest"|"all" }`: batch transaction import

### Settings Routes (`backend/routes/settings.py`)
- `GET /api/settings/get`: returns configuration values (masks sensitive data like tushare_token)
- `POST /api/settings/update` with `{ updates: Record<string, any> }`: updates configuration keys

### Reference Data Routes (`backend/routes/reference_data.py`)
- `GET /api/category/list`: all categories for dropdowns
- `POST /api/category/create`: create new category
- `POST /api/category/update`: update category
- `POST /api/category/bulk-update`: bulk category updates
- `GET /api/instrument/list` (optional `q`, `active_only=true`): autocomplete instrument list
- `GET /api/instrument/get` (`ts_code`): instrument detail with category names
- `POST /api/instrument/create`: creates/updates instrument mapping with optional recalculation
- `POST /api/instrument/update`: toggles instrument active status
- `POST /api/instrument/edit`: edit instrument base fields
- `POST /api/seed/load` (categories_csv, instruments_csv, optional `recalc_today`): loads seed data

### Position Routes (`backend/routes/positions.py`)
- `GET /api/position/raw`: returns raw positions for maintenance
- `POST /api/position/opening`: set opening position
- `POST /api/position/update` with `{ ts_code, shares?, avg_cost?, date, opening_date? }`: upsert position
- `POST /api/position/delete` with `{ ts_code, recalc_date? }`: delete position

### Pricing Routes (`backend/routes/pricing.py`)
- `POST /api/sync-prices` with `{ date, recalc }`: syncs EOD prices via TuShare with optional recalculation
- `GET /api/price/last` (`ts_code`, optional `date`): last price as of date
- `GET /api/price/ohlc` (`ts_code`, `start`, `end` YYYYMMDD): OHLC range for K-line charts
- `GET /api/instrument/lookup` (`ts_code`, optional `date=YYYYMMDD`): instrument lookup with TuShare integration

### Analytics Routes (`backend/routes/analytics.py`)
- `GET /api/position/irr` (`ts_code`, optional `date`): IRR calculation for single instrument
- `GET /api/position/irr/batch` (optional `date`): batch IRR calculations for all positions

### Reports Routes (`backend/routes/reports.py`)
- `POST /api/calc` with `{ date }`: triggers recomputation pipeline

### Logs Routes (`backend/routes/logs.py`)
- Log-related endpoints for operation tracking and debugging

### Maintenance Routes (`backend/routes/maintenance.py`)
- `POST /api/backup`: dumps business tables as JSON with downloadable response
- `POST /api/restore` (multipart file): transactional restore of business tables

## Key Services & Utilities (unchanged)
- `services/config_svc.py`: configuration management with defaults and typed access
- `services/position_svc.py`: CRUD operations for base positions
- `services/dashboard_svc.py`: aggregated views for dashboard/category/position/signal
- `services/signal_svc.py`: automatic and manual signal creation with structure signal rebuilders
- `services/pricing_svc.py` + `providers/tushare_provider.py`: external price sync with rate limiting
- `services/calc_svc.py`: recomputation pipeline for portfolio_daily, category_daily, signals
- `services/analytics_svc.py`: IRR/XIRR calculations for instruments and batch operations
- `services/position_status_svc.py`: real-time thresholds (stop gain/loss) and alert counts
- `services/txn_svc.py`: transaction persistence and side-effects
- `services/watchlist_svc.py`: watchlist management operations
- `services/utils.py`: date helpers and rounding utilities

## Architecture Benefits
- **Separation of concerns**: Each route module handles a specific business domain
- **Maintainability**: Easier to locate and modify specific functionality
- **Scalability**: New features can be added to appropriate modules without affecting others
- **Testing**: Individual route modules can be tested in isolation
- **Clean entry point**: `backend/api.py` focuses only on app setup and router registration

## Data Model & Database (unchanged)
- See `schema.sql` for tables: `config`, `category`, `instrument`, `txn`, `price_eod`, `ma_cache`, `position`, `portfolio_daily`, `category_daily`, `signal`, `operation_log`
- DB path resolution via `backend/db.py#get_db_path` with environment variable support
- Logging via `backend/logs.py` with `LogContext` for structured audit logging

## Frontend Integration (unchanged)
- Axios client base: `VITE_API_BASE` or `http://127.0.0.1:8000`
- React Query hooks map to endpoints in `frontend/src/api/hooks.ts`
- UI pages consume modular API endpoints seamlessly
- Charts use OHLC and position series from pricing and dashboard routes

## Development & Operations
- Start: `bash scripts/dev.sh` or `bash scripts/dev-fast.sh`
- Backend: `uvicorn backend.api:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev`
- Tests: `pytest` from project root targeting individual route modules and services

## Conventions & Behaviors (unchanged)
- All write operations trigger `calc()` for affected dates
- Frontend expects `YYYYMMDD` format for most date queries
- Price fallback logic when EOD prices are missing
- Transactional operations with proper error handling and logging