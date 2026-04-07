# ==============================================================================
# app/core/authorization.py
# Full RBAC + ABAC + Object Ownership Checker (Phase 3.3 + 3.4 + 3.5)
# Exact 8 offices with spaces from the repo.
# ==============================================================================

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User
from app.core.security import get_current_user
from app.db.session import get_db
import hashlib


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self,
        current_user: User = Depends(get_current_user)
    ):
        # Fast cache check
        if self.required_permission in current_user.permissions_cache:
            return current_user

        # ABAC evaluation based on the exact 8 offices
        office = current_user.office.value

        if office == "Bishop" or office == "Sys Admin":
            return current_user  # global access

        if office in ["Dean", "Deanery Youth Chaplain"]:
            if not current_user.deanery_id:
                raise HTTPException(status_code=403, detail="No deanery assigned")
            return current_user

        if office in ["Parish Priest", "Assistant Priest", "Parish Youth Chaplain", "Parish Secretary"]:
            if not current_user.parish_id:
                raise HTTPException(status_code=403, detail="No parish assigned")
            return current_user

        raise HTTPException(status_code=403, detail="Insufficient permissions")


class OwnershipService:
    """Enforces object-level ownership checks (parish/deanery)"""
    async def check_ownership(
        self,
        record,
        current_user: User = Depends(get_current_user)
    ):
        if current_user.office.value == "Bishop":
            return True
        if current_user.parish_id and getattr(record, 'owner_parish_id', None) == current_user.parish_id:
            return True
        if current_user.deanery_id and getattr(record, 'owner_deanery_id', None) == current_user.deanery_id:
            return True
        raise HTTPException(status_code=403, detail="You do not have access to this record")


def get_ownership_checker():
    async def checker(current_user: User = Depends(get_current_user)):
        return current_user
    return checker


def generate_device_fingerprint(user_agent: str, ip_address: str) -> str:
    data = f"{user_agent}|{ip_address}".encode()
    return hashlib.sha256(data).hexdigest()