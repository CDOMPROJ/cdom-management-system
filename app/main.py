from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# ==========================================
# 1. ROUTER IMPORTS
# ==========================================
from app.api.v1 import (
    auth,
    admin,
    audit,
    baptisms,
    first_communions,
    confirmations,
    marriages,
    death_register,
    analytics,
    search,
    approvals,
    finances,
    umutulo,
    certificates,
    youth_ministry
)

# ==========================================
# 2. APP INITIALIZATION
# ==========================================
# We use settings.PROJECT_NAME which pulls securely from your .env file via config.py
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Management System for the Catholic Diocese of Mansa (CDOM)",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==========================================
# 3. CORS MIDDLEWARE
# ==========================================
# Essential for allowing Flutter (or Web Frontends) to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace "*" with your app's specific domain/IP
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allows all headers (like Authorization: Bearer)
)

# ==========================================
# 4. ROUTER REGISTRATION
# ==========================================

# SECTION 1: Identity & Access Management (IAM)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["1.0 Authentication & IAM"])

# SECTION 2: Executive Oversight
app.include_router(admin.router, prefix="/api/v1/admin", tags=["2.0 Bishop's Dashboard"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["2.2 Governance & Audit Trail"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["4.0 The Gold Layer"])

# SECTION 3 & 4 & 5: Sacramental Registers (Parish Level)
app.include_router(search.router, prefix="/api/v1/search", tags=["3.0 Intelligence Layer"])
app.include_router(baptisms.router, prefix="/api/v1/baptisms", tags=["3.0 Register: Baptisms"])
app.include_router(first_communions.router, prefix="/api/v1/first-communions", tags=["3.1 Register: First Communion"])
app.include_router(confirmations.router, prefix="/api/v1/confirmations", tags=["3.2 Register: Confirmations"])
app.include_router(marriages.router, prefix="/api/v1/marriages", tags=["4.0 Register: Marriages"])
app.include_router(death_register.router, prefix="/api/v1/deaths", tags=["5.0 Register: Liber Defunctorum (Deaths)"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["2.1 Governance & Approvals"])

# SECTION 6: Financial Management
app.include_router(finances.router, prefix="/api/v1/finances", tags=["6.0 Parish Ledger"])
app.include_router(umutulo.router, prefix="/api/v1/umutulo", tags=["6.1 CDOM Obligations (Umutulo)"])

# SECTION 7: Official Documents
app.include_router(certificates.router, prefix="/api/v1/print", tags=["7.0 Official Certificates"])

# SECTION 8: Pastoral Care & Formation
app.include_router(youth_ministry.router, prefix="/api/v1/youth", tags=["8.0 Youth Ministry & Catechesis"])

# ==========================================
# 5. SYSTEM HEALTH CHECK
# ==========================================
@app.get("/", tags=["System Status"])
async def root():
    """Returns the current operational status of the CDOM backend."""
    return {
        "system": settings.PROJECT_NAME,
        "status": "Online",
        "version": "1.3.0",
        "message": "Welcome to the Catholic Diocese of Mansa Management System."
    }