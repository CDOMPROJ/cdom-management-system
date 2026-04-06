# ==============================================================================
# app/main.py
# FastAPI entry point with Phase 3.3 background session cleanup
# ==============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import router as v1_router
import asyncio
from datetime import datetime, timedelta, timezone
from app.db.session import get_db
from app.models.all_models import UserSession
from sqlalchemy import select, delete

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def cleanup_expired_sessions():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            async with get_db() as db:
                # Idle 30 min and absolute 24 h cleanup
                cutoff_idle = datetime.now(timezone.utc) - timedelta(minutes=30)
                cutoff_absolute = datetime.now(timezone.utc) - timedelta(hours=24)
                await db.execute(delete(UserSession).where(
                    (UserSession.last_active < cutoff_idle) | (UserSession.expires_at < cutoff_absolute)
                ))
                await db.commit()
    task = asyncio.create_task(cleanup_expired_sessions())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan, title="CDOM Pastoral Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)

@app.get("/health")
async def health():
    return {"status": "healthy"}