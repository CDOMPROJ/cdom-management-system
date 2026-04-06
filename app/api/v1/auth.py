# ==============================================================================
# app/api/v1/auth.py
# Full Phase 3.4 Auth Router – Session tracking, elevated tokens, trusted devices
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, generate_device_fingerprint
from app.models.all_models import User, UserSession, ElevatedToken
from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/auth", tags=["auth"])

class SessionResponse(BaseModel):
    id: str
    device_fingerprint: str
    ip_address: str
    user_agent: str
    last_active: datetime
    is_trusted: bool

class ElevatedTokenRequest(BaseModel):
    reason: str

# Session Tracking API
@router.get("/sessions", response_model=List[SessionResponse])
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UserSession).where(UserSession.user_id == current_user.id)
    )
    return result.scalars().all()

@router.post("/sessions/{session_id}/logout")
async def logout_specific_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(UserSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": "Session logged out successfully"}

# Elevated Access Token (Bishop-only)
@router.post("/elevate")
async def create_elevated_token(
    request: ElevatedTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can create elevated tokens")
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    elevated = ElevatedToken(
        token=token,
        user_id=current_user.id,
        expires_at=expires_at,
        reason=request.reason
    )
    db.add(elevated)
    await db.commit()
    return {"token": token, "expires_at": expires_at.isoformat()}

# Trusted Device Management
@router.post("/devices/trust")
async def trust_device(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    fingerprint = generate_device_fingerprint(ua, ip)
    session = UserSession(
        user_id=current_user.id,
        device_fingerprint=fingerprint,
        ip_address=ip,
        user_agent=ua,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_trusted=True
    )
    db.add(session)
    await db.commit()
    return {"message": "Device marked as trusted", "fingerprint": fingerprint}