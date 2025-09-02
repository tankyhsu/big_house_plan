# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Quick Start
```bash
# Full setup with dependency installation
bash scripts/dev.sh

# Quick start (assumes dependencies already installed)
bash scripts/dev-fast.sh
```

### Backend (Python/FastAPI)
```bash
# Manual backend setup
python -m venv .venv
source .venv/bin/activate  # Windows Git Bash: source .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
uvicorn backend.api:app --reload --port 8000

# Run tests
pytest  # Run from project root

# Test specific file
pytest backend/tests/test_calc_smoke.py
```

### Frontend (React/TypeScript)
```bash
cd frontend

# Install dependencies  
npm i

# Development server
npm run dev

# Build
npm run build

# Lint
npm run lint
```

### Configuration
- First run generates `config.yaml` with default settings
- Frontend uses `frontend/.env` with `VITE_API_BASE=http://127.0.0.1:8000`
- TuShare token configuration in config.yaml enables price synchronization

## Architecture

This is a **portfolio management system** with FastAPI backend and React frontend.

### Core Components

**Backend (`backend/`)**
- `api.py` - FastAPI routes grouped by functional domain
- `services/` - Business logic layer:
  - `calc_svc.py` - Portfolio calculations and rebalancing logic
  - `pricing_svc.py` - Price synchronization via TuShare API
  - `dashboard_svc.py` - Dashboard aggregations and KPIs
  - `txn_svc.py` - Transaction processing
  - `position_svc.py` - Position management
- `repository/` - Data access layer with SQLite operations
- `domain/txn_engine.py` - Core transaction engine with position calculations
- `providers/tushare_provider.py` - External price data integration

**Frontend (`frontend/src/`)**
- `pages/` - Main application views (Dashboard, Review, Transaction entry, Settings)
- `components/charts/` - ECharts-based visualizations including candlestick charts
- `api/` - Type-safe API client and React Query hooks

### Key Data Flow
1. Transactions → Position calculations via transaction engine → Portfolio snapshots
2. Price sync from TuShare → Daily recalculation of all metrics
3. All write operations trigger automatic recalculation for affected trading dates

### Database Design
- SQLite with schema defined in `schema.sql`
- Key tables: instruments, categories, positions, transactions, portfolio (daily snapshots)
- Seeds data in `seeds/` directory (categories.csv, instruments.csv)

### Configuration & Environment
- `config.yaml` - Main configuration (database path, trading parameters, TuShare token)
- Environment variable `PORT_DB_PATH` can override database location
- Test mode uses `test_db_path` configuration

## Testing

- Backend tests in `backend/tests/` using pytest
- Run `pytest` from project root
- Tests include transaction engine, calculation services, and API integration
- Frontend linting available via `npm run lint`