# ==============================================================================
# app/main.py
# PRODUCTION MAIN ENTRY POINT – CORRECT MIDDLEWARE PLACEMENT
# ==============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.core.config import settings
from app.api.v1.router import router as v1_router
from app.core.security import AuthMiddleware
from app.core.authorization import PermissionChecker

# ==============================================================================
# LIFESPAN (STARTUP / SHUTDOWN)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background cleanup task for sessions
    async def cleanup_expired_sessions():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            # Full cleanup will be implemented in next phase
            pass

    task = asyncio.create_task(cleanup_expired_sessions())
    yield
    task.cancel()


# ==============================================================================
# FASTAPI APP
# ==============================================================================
app = FastAPI(
    title="CDOM Pastoral Management System",
    description="Backend for Catholic Diocese of Mansa Management System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ==============================================================================
# MIDDLEWARE (MUST BE ON FastAPI APP, NOT ON APIRouter)
# ==============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom security middleware
app.add_middleware(AuthMiddleware)

# ==============================================================================
# INCLUDE V1 ROUTER
# ==============================================================================
app.include_router(v1_router, prefix="/api/v1", tags=["v1"])


# ==============================================================================
# HEALTH CHECK
# ==============================================================================
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "CDOM Backend"}


# ==============================================================================
# OPTIONAL: GLOBAL EXCEPTION HANDLER
# ==============================================================================
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


print("🚀 CDOM Backend started successfully!")