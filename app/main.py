from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# ==============================================================================
# 1. ROUTER IMPORTS
# ==============================================================================
from app.api.v1 import (
    # Identity & Access Management
    auth,
    users,

    # Executive & Administration
    bishop,
    quinquennial_vatican_report,
    deanery,
    audit,
    approvals,

    # Core Data & Analytics
    analytics,
    search,

    # Sacramental Registers
    baptisms,
    first_communions,
    confirmations,
    marriages,
    death_register,

    # Financial Engine
    finances,

    # Pastoral Care
    youth_ministry,

    # Utilities
    certificates,
    communications
)

# ==============================================================================
# 2. APP INITIALIZATION
# ==============================================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Management System for the Catholic Diocese of Mansa (CDOM)",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==============================================================================
# 3. CORS MIDDLEWARE
# ==============================================================================
# Essential for allowing external frontends (React/Flutter) to communicate securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allows all headers (like Authorization: Bearer)
)

# ==============================================================================
# 4. ROUTER REGISTRATION (ARCHITECTURAL TIERS)
# ==============================================================================

# --- TIER 1: Identity & Access Management (IAM) ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["1.0 Authentication & IAM"])
app.include_router(users.router, prefix="/api/v1/users", tags=["1.1 Users & Provisioning"])

# --- TIER 2: Executive Oversight & Governance ---
app.include_router(bishop.router, prefix="/api/v1/bishop", tags=["2.0 Executive: Bishop's Dashboard"])
app.include_router(quinquennial_vatican_report.router, prefix="/api/v1/admin", tags=["2.1 Executive: System Admin"])
app.include_router(deanery.router, prefix="/api/v1/deanery", tags=["2.2 Executive: Deanery Management"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["2.3 Governance: Pending Approvals"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["2.4 Governance: Immutable Audit Trail"])

# --- TIER 3: The Canonical Sacramental Registers ---
app.include_router(baptisms.router, prefix="/api/v1/baptisms", tags=["3.0 Register: Baptisms"])
app.include_router(first_communions.router, prefix="/api/v1/first-communions", tags=["3.1 Register: First Communions"])
app.include_router(confirmations.router, prefix="/api/v1/confirmations", tags=["3.2 Register: Confirmations"])
app.include_router(marriages.router, prefix="/api/v1/marriages", tags=["3.3 Register: Holy Matrimony"])
app.include_router(death_register.router, prefix="/api/v1/deaths", tags=["3.4 Register: Liber Defunctorum (Deaths)"])

# --- TIER 4: Financial Management ---
app.include_router(finances.router, prefix="/api/v1/finances", tags=["4.0 Finance: Parish Ledger"])

# --- TIER 5: Pastoral Care & Formation ---
app.include_router(youth_ministry.router, prefix="/api/v1/youth", tags=["5.0 Pastoral: Youth Ministry & Catechesis"])

# --- TIER 6: Intelligence & Data Warehouse ---
app.include_router(search.router, prefix="/api/v1/search", tags=["6.0 Intelligence: Global Search"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["6.1 Intelligence: The Gold Layer (Analytics)"])

# --- TIER 7: System Utilities & Output ---
app.include_router(certificates.router, prefix="/api/v1/print", tags=["7.0 Utilities: Official Certificates (PDF)"])
app.include_router(communications.router, prefix="/api/v1/communications",
                   tags=["7.1 Utilities: Email & Notifications"])


# ==============================================================================
# 5. SYSTEM HEALTH CHECK
# ==============================================================================
@app.get("/", tags=["System Status"])
async def root():
    """Returns the current operational status of the CDOM backend."""
    return {
        "system": settings.PROJECT_NAME,
        "status": "Online",
        "version": "1.3.0",
        "message": "Welcome to the Catholic Diocese of Mansa Management System API."
    }