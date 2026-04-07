# ==============================================================================
# app/api/v1/router.py
# CENTRAL ROUTER – All routes aggregated (flat app/api/v1 structure)
# Includes new clergy_registry router + optimized imports, CORS, rate limiting, logging
# ==============================================================================

import logging
import time
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.core.authorization import PermissionChecker, get_ownership_checker
from app.core.security import get_current_user

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ==============================================================================
# RATE LIMITER
# ==============================================================================
RATE_LIMIT = 100
RATE_WINDOW = 60
ip_request_log = defaultdict(list)

async def rate_limiter(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    ip_request_log[ip] = [t for t in ip_request_log[ip] if now - t < RATE_WINDOW]
    if len(ip_request_log[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per {RATE_WINDOW} seconds.")
    ip_request_log[ip].append(now)
    return True

# ==============================================================================
# AUTHORIZATION MIDDLEWARE WITH STRUCTURED LOGGING
# ==============================================================================
from starlette.middleware.base import BaseHTTPMiddleware

class AuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]
        user_email = "anonymous"
        ip = request.client.host if request.client else "unknown"

        logger.info(f"REQUEST | id={request_id} | method={request.method} | path={request.url.path} | user={user_email} | ip={ip}")

        try:
            response = await call_next(request)
            duration = time.time() - start_time
            logger.info(f"RESPONSE | id={request_id} | status={response.status_code} | path={request.url.path} | user={user_email} | duration={duration:.3f}s")
            return response
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(f"ERROR | id={request_id} | type={type(exc).__name__} | path={request.url.path} | user={user_email} | duration={duration:.3f}s | traceback={traceback.format_exc()}")
            return await self.handle_exception(request, exc)

    async def handle_exception(self, request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Add CORS
router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware and rate limiter
router.add_middleware(AuthorizationMiddleware)
router.dependencies = [Depends(rate_limiter)]

# ==============================================================================
# CLEAN IMPORTS – All routes (including new clergy_registry)
# ==============================================================================
from .auth import router as auth_router
from .baptisms import router as baptisms_router
from .marriages import router as marriage_router
from .confirmation import router as confirmation_router
from .first_communions import router as first_communion_router
from .death_register import router as death_register_router
from .finances import router as finances_router
from .clergy_registry import router as clergy_registry_router
from .youth_ministry import router as youth_ministry_router
from .analytics import router as analytics_router
from .approvals import router as approvals_router
from .audit import router as audit_router
from .bishop import router as bishop_router
from .certificates import router as certificates_router
from .communications import router as communications_router
from .deanery import router as deanery_router
from .quinquennial_vatican_report import router as quinquennial_vatican_report_router
from .search import router as search_router
from .users import router as users_router

# Include all routers
router.include_router(auth_router)
router.include_router(baptisms_router)
router.include_router(marriage_router)
router.include_router(confirmation_router)
router.include_router(first_communion_router)
router.include_router(death_register_router)
router.include_router(finances_router)
router.include_router(clergy_registry_router)
router.include_router(youth_ministry_router)
router.include_router(analytics_router)
router.include_router(approvals_router)
router.include_router(audit_router)
router.include_router(bishop_router)
router.include_router(certificates_router)
router.include_router(communications_router)
router.include_router(deanery_router)
router.include_router(quinquennial_vatican_report_router)
router.include_router(search_router)
router.include_router(users_router)

# ==============================================================================
# GLOBAL ERROR HANDLING
# ==============================================================================
@router.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"VALIDATION_ERROR | path={request.url.path} | errors={exc.errors()}")
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}))

@router.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    logger.error(f"INTEGRITY_ERROR | path={request.url.path} | error={str(exc)}")
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Database integrity error – duplicate or invalid data"})

@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP_ERROR | path={request.url.path} | status={exc.status_code} | detail={exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"UNEXPECTED_ERROR | path={request.url.path} | traceback={traceback.format_exc()}")
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error – please contact support"})