"""
FastAPI app entry point aggregating per-domain routers under backend/routes.
Keep as `uvicorn backend.api:app`.
"""
from __future__ import annotations


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .logs import ensure_log_schema, OperationLogContext
from .services.config_svc import ensure_default_config
from .services.watchlist_svc import ensure_watchlist_schema


app = FastAPI(title="portfolio-ui-api", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_log_schema()
    ensure_default_config()
    try:
        ensure_watchlist_schema()
    except Exception as e:
        OperationLogContext("STARTUP").write("ERROR", f"ensure_watchlist_schema_failed: {e}")


# Include routers (split by business domain)
from .routes import base as base_routes
from .routes import dashboard as dashboard_routes
from .routes import signals as signals_routes
from .routes import watchlist as watchlist_routes
from .routes import settings as settings_routes
from .routes import reference_data as reference_routes
from .routes import transactions as transactions_routes
from .routes import positions as positions_routes
from .routes import pricing as pricing_routes
from .routes import analytics as analytics_routes
from .routes import logs as logs_routes
from .routes import maintenance as maintenance_routes
from .routes import reports as reports_routes

app.include_router(base_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(signals_routes.router)
app.include_router(watchlist_routes.router)
app.include_router(settings_routes.router)
app.include_router(reference_routes.router)
app.include_router(transactions_routes.router)
app.include_router(positions_routes.router)
app.include_router(pricing_routes.router)
app.include_router(analytics_routes.router)
app.include_router(logs_routes.router)
app.include_router(maintenance_routes.router)
app.include_router(reports_routes.router)
