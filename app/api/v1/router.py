# ==============================================================================
# app/api/v1/router.py
# CENTRAL V1 ROUTER – FULLY ACTIVE (ALL ROUTES INCLUDED)
# ==============================================================================

from fastapi import APIRouter

# Import all routers
from app.api.v1.auth import router as auth_router
from app.api.v1.baptisms import router as baptism_router
from app.api.v1.marriages import router as marriage_router
from app.api.v1.confirmation import router as confirmation_router
from app.api.v1.first_communions import router as first_communion_router
from app.api.v1.death_register import router as death_register_router
from app.api.v1.finances import router as finance_router
from app.api.v1.clergy_registry import router as clergy_registry_router
from app.api.v1.youth_ministry import router as youth_ministry_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.bishop import router as bishop_router
from app.api.v1.certificates import router as certificates_router
from app.api.v1.communications import router as communications_router
from app.api.v1.deanery import router as deanery_router
from app.api.v1.quinquennial_vatican_report import router as quinquennial_vatican_report_router
from app.api.v1.search import router as search_router
from app.api.v1.users import router as users_router

# Main v1 router
router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include ALL routers (no commenting out)
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(baptism_router, prefix="/baptisms", tags=["baptisms"])
router.include_router(marriage_router, prefix="/marriages", tags=["marriages"])
router.include_router(confirmation_router, prefix="/confirmations", tags=["confirmations"])
router.include_router(first_communion_router, prefix="/first-communions", tags=["first-communions"])
router.include_router(death_register_router, prefix="/deaths", tags=["deaths"])
router.include_router(finance_router, prefix="/finances", tags=["finances"])
router.include_router(clergy_registry_router, prefix="/clergy", tags=["clergy"])
router.include_router(youth_ministry_router, prefix="/youth", tags=["youth"])
router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
router.include_router(audit_router, prefix="/audit", tags=["audit"])
router.include_router(bishop_router, prefix="/bishop", tags=["bishop"])
router.include_router(certificates_router, prefix="/certificates", tags=["certificates"])
router.include_router(communications_router, prefix="/communications", tags=["communications"])
router.include_router(deanery_router, prefix="/deaneries", tags=["deaneries"])
router.include_router(quinquennial_vatican_report_router, prefix="/quinquennial", tags=["quinquennial"])
router.include_router(search_router, prefix="/search", tags=["search"])
router.include_router(users_router, prefix="/users", tags=["users"])


@router.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "CDOM Backend"}