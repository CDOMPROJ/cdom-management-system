from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.security import SecurityHeadersMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_fastapi import PrometheusMiddleware
import logging

from app.core.config import settings
from app.schemas.error import ErrorResponse

from app.api.v1 import (
    auth, users, bishop, quinquennial_vatican_report, deanery, audit, approvals,
    analytics, search, baptisms, first_communions, confirmations, marriages,
    death_register, finances, youth_ministry, certificates, communications,
    ml_router, base_crud
)

# Logger for security events
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Management System for the Catholic Diocese of Mansa (CDOM)",
    version="1.5.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class AuthMiddleware(BaseHTTPMiddleware):
    """Custom middleware to enforce JWT authentication on all protected routes.
    Revised for better error handling and logging."""
    async def dispatch(self, request: Request, call_next):
        # Skip auth check for public routes
        if request.url.path.startswith("/api/v1/auth") or request.url.path == "/":
            return await call_next(request)

        # Check for Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"Missing or invalid token for path: {request.url.path}")
            return ErrorResponse(detail="Missing or invalid Authorization header")

        # Token is present - let the dependency in the router handle validation
        return await call_next(request)

# Production security middleware stack
app.add_middleware(PrometheusMiddleware)          # Metrics collection
app.add_middleware(HTTPSRedirectMiddleware)       # Force HTTPS in production
app.add_middleware(SecurityHeadersMiddleware)     # Security headers (X-Frame-Options, etc.)
app.add_middleware(AuthMiddleware)                # Revised JWT middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cdom-app.web.app", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router registration with clear tiered organization
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
app.include_router(certificates.router, prefix="/api/v1/print", tags=["7.0 Utilities: Official Certificates (PDF)"])
app.include_router(communications.router, prefix="/api/v1/communications", tags=["7.1 Utilities: Email & Notifications"])

@app.get("/", tags=["System Status"])
async def root():
    """Returns the current operational status of the CDOM backend."""
    return {"system": settings.PROJECT_NAME, "status": "Online", "version": "1.5.0"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return {"message": "Prometheus metrics available at /metrics"}