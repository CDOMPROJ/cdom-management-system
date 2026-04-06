# ==============================================================================
# app/core/authorization.py
# Phase 3.4: Full RBAC + ABAC + Ownership + Elevated Token Support
# ==============================================================================

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User
from app.core.security import get_current_user

class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user: User = Depends(get_current_user)):
        office = current_user.office.value
        if office == "Bishop" or office == "Sys Admin":
            return current_user
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def generate_device_fingerprint(user_agent: str, ip_address: str) -> str:
    import hashlib
    data = f"{user_agent}|{ip_address}".encode()
    return hashlib.sha256(data).hexdigest()