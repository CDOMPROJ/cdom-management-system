# ==========================================
# CDOM Pastoral Management System – Main Entry Point
# FastAPI + Lifespan Auto-Migrations + SecurityPatch Middleware
# ==========================================

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.security import AuthMiddleware   # ← SecurityPatch AuthMiddleware
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.api.v1 import (
    auth, users, bishop, quinquennial_vatican_report, deanery, audit, approvals,
    analytics, search, baptisms, first_communions, confirmations, marriages,
    death_register, finances, youth_ministry, certificates, communications,
    ml_router, base_crud
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment in ["development", "staging"]:
        print("🚀 Running Alembic migrations automatically...")
        try:
            subprocess.check_call(["alembic", "upgrade", "head"])
            print("✅ Migrations completed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Migration warning: {e}")
    else:
        print("🛡️ Production mode - migrations must be run manually before deployment.")
    yield
    print("👋 Shutting down CDOM backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Management System for the Catholic Diocese of Mansa (CDOM)",
    version="1.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ==================== SECURITY MIDDLEWARE STACK ====================
app.add_middleware(PrometheusMiddleware)          # ← This was missing in some versions
app.add_middleware(HTTPSRedirectMiddleware)

# SecurityPatch AuthMiddleware (protects all protected routes)
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
Instrumentator().instrument(app).expose(app, include_in_schema=False)


# ==================== ROUTER REGISTRATION ====================
app.include_router(auth.router, prefix="/api/v1/auth", tags=["1.0 Authentication & IAM"])
app.include_router(users.router, prefix="/api/v1/users", tags=["1.1 Users & Provisioning"])
app.include_router(bishop.router, prefix="/api/v1/bishop", tags=["2.0 Executive: Bishop's Dashboard"])
app.include_router(quinquennial_vatican_report.router, prefix="/api/v1/bishop", tags=["2.0 Executive: Bishop's Dashboard"])
app.include_router(deanery.router, prefix="/api/v1/deanery", tags=["2.2 Executive: Deanery Management"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["2.3 Governance: Pending Approvals"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["2.4 Governance: Immutable Audit Trail"])
app.include_router(baptisms.router, prefix="/api/v1/baptisms", tags=["3.0 Register: Baptisms"])
app.include_router(first_communions.router, prefix="/api/v1/first-communions", tags=["3.1 Register: First Communions"])
app.include_router(confirmations.router, prefix="/api/v1/confirmations", tags=["3.2 Register: Confirmations"])
app.include_router(marriages.router, prefix="/api/v1/marriages", tags=["3.3 Register: Holy Matrimony"])
app.include_router(death_register.router, prefix="/api/v1/deaths", tags=["3.4 Register: Liber Defunctorum (Deaths)"])
app.include_router(finances.router, prefix="/api/v1/finances", tags=["4.0 Finance: Parish Ledger"])
app.include_router(youth_ministry.router, prefix="/api/v1/youth", tags=["5.0 Pastoral: Youth Ministry & Catechesis"])
app.include_router(search.router, prefix="/api/v1/search", tags=["6.0 Intelligence: Global Search"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["6.1 Intelligence: The Gold Layer (Analytics)"])
app.include_router(ml_router.router, prefix="/api/v1/ml", tags=["6.2 Intelligence: ML Router"])
app.include_router(base_crud.router, prefix="/api/v1", tags=["Base CRUD"])

@app.get("/", tags=["System Status"])
async def root():
    return {"system": settings.PROJECT_NAME, "status": "Online", "version": "1.5.0"}


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    return {"message": "Prometheus metrics available at /metrics"}