# ==========================================
# CDOM Pastoral Management System – Auth Router (Flat Structure)
# SecurityPatch – JWT + Revocation + Refresh Rotation
# ==========================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    revoke_token,
    revoke_all_user_tokens,
    is_token_revoked,
    decode_token
)
from app.models.user import User
from app.schemas.schemas import (
    LoginRequest,
    Token,
    TokenRefresh,
    PasswordChangeRequest
)
from jose.exceptions import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(form_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.email).first()
    if not user or not verify_password(form_data.password, user.password_hash):  # type: ignore
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not user.is_active:  # type: ignore
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(user.id, user.token_version)  # type: ignore
    refresh_token = create_refresh_token(user.id, user.token_version)  # type: ignore

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: TokenRefresh, db: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")

        user_id = payload["sub"]
        token_version = payload["version"]
        jti = payload["jti"]

        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.token_version != token_version or is_token_revoked(db, jti):  # type: ignore
            raise HTTPException(status_code=401, detail="Token revoked or invalid")

        new_access = create_access_token(user.id, user.token_version)  # type: ignore
        new_refresh = create_refresh_token(user.id, user.token_version)  # type: ignore

        return Token(access_token=new_access, refresh_token=new_refresh)

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
async def logout(authorization: str = Depends(lambda request: request.headers.get("authorization")),
                 db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = decode_token(token)
        jti = payload["jti"]
        user_id = payload["sub"]
        revoke_token(db, jti, user_id, reason="logout")
        return {"message": "Successfully logged out"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/logout-all")
async def logout_all_devices(authorization: str = Depends(lambda request: request.headers.get("authorization")),
                             db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
        revoke_all_user_tokens(db, user_id)
        return {"message": "Logged out from all devices"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/change-password")
async def change_password(request: PasswordChangeRequest,
                          authorization: str = Depends(lambda request: request.headers.get("authorization")),
                          db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.password_hash = get_password_hash(request.new_password)  # type: ignore
        revoke_all_user_tokens(db, user_id)
        db.commit()

        return {"message": "Password changed successfully. Logged out from all devices."}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")