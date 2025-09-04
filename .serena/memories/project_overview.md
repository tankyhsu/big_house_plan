# Portfolio Management System - Project Overview

## Purpose
A comprehensive portfolio management system with FastAPI backend and React frontend for tracking investments, calculating returns, and generating trading signals.

## Tech Stack
- **Backend**: Python, FastAPI, SQLite, pandas
- **Frontend**: React, TypeScript, ECharts for visualizations
- **Testing**: pytest for backend tests
- **Development**: uvicorn for backend, Vite for frontend dev server

## Core Architecture

### Backend Structure
- `api.py` - FastAPI routes grouped by functional domain
- `services/` - Business logic layer
  - `calc_svc.py` - Portfolio calculations and rebalancing
  - `signal_svc.py` - Signal generation and management  
  - `dashboard_svc.py` - Dashboard data aggregation
  - `pricing_svc.py` - Price sync via TuShare API
- `repository/` - Data access layer with SQLite operations
- `domain/txn_engine.py` - Core transaction engine
- `providers/tushare_provider.py` - External price data

### Key Data Flow
1. Transactions → Position calculations → Portfolio snapshots
2. Price sync from TuShare → Daily recalculation 
3. Signal generation based on position thresholds

### Database Schema
- SQLite with key tables: instruments, categories, positions, transactions, portfolio_daily, signal
- Daily snapshots stored in portfolio_daily and category_daily tables

## Current Signal System Design Issues
The system has stop-gain/stop-loss signals that are currently implemented as time-dependent events, but should be objective calculations based on cost vs current price.