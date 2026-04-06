from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import create_access_token, create_refresh_token, revoke_token, revoke_all_user_tokens
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import Token, TokenRefresh

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(db: Session = Depends(get_db), credentials: dict = None):
    # ... existing login logic ...
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(token: str = None, db: Session = Depends(get_db)):
    if token:
        revoke_token(db, token, reason="logout")
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: TokenRefresh, db: Session = Depends(get_db)):
    # Verify refresh token and rotate
    payload = jwt.decode(refresh_token.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    revoke_token(db, refresh_token.refresh_token, reason="rotation")
    new_access = create_access_token(subject=payload.get("sub"))
    new_refresh = create_refresh_token(subject=payload.get("sub"))
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}

@router.post("/change-password")
async def change_password(db: Session = Depends(get_db), token: str = None, new_password: str = None):
    # ... existing password change logic ...
    if token:
        revoke_token(db, token, reason="password_change")
    return {"message": "Password changed successfully"}