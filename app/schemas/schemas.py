from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Generic, TypeVar, Dict, Any
from datetime import date, datetime
import uuid
import enum
import re

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total_count: int
    limit: int
    skip: int
    data: List[T]


class ReligionCategory(str, enum.Enum):
    CATHOLIC = "Catholic"
    OTHER_CHRISTIAN = "Other Christian"
    NON_CHRISTIAN = "Non-Christian"


# ==============================================================================
# 0. EXECUTIVE GEOGRAPHY (DEANERIES & PARISHES)
# ==============================================================================
class DeaneryBase(BaseModel):
    name: str

class DeaneryCreate(DeaneryBase):
    pass

class DeaneryResponse(DeaneryBase):
    id: int

    class Config:
        from_attributes = True

class ParishBase(BaseModel):
    name: str
    deanery_id: int
    schema_name: str

class ParishCreate(ParishBase):
    pass

class ParishResponse(ParishBase):
    id: int

    class Config:
        from_attributes = True


# ==============================================================================
# 1. AUTHENTICATION, USERS & MFA
# ==============================================================================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    mfa_required: bool = False
    temp_token: Optional[str] = None
    message: Optional[str] = None


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    temp_token: Optional[str] = None
    code: str


class UserInviteRequest(BaseModel):
    email: EmailStr
    personal_email: EmailStr
    role: str
    parish_id: Optional[int] = None
    deanery_id: Optional[int] = None


class UserSetupRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str

    @field_validator('password')
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError('Password must contain at least one special character')
        return v


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str
    parish_id: Optional[int] = None
    deanery_id: Optional[int] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    is_active: bool
    mfa_enabled: bool
    parish_id: Optional[int] = None

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, description="Must be at least 8 characters")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Must be at least 8 characters")


class DirectUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str
    office: str
    parish_id: int | None = None
    deanery_id: int | None = None


# Explicit imports of split sacramental schemas
from app.schemas.baptism import BaptismBase, BaptismCreate, BaptismResponse
from app.schemas.marriage import MarriageBase, MarriageCreate, MarriageResponse
from app.schemas.first_communion import FirstCommunionBase, FirstCommunionCreate, FirstCommunionResponse
from app.schemas.confirmation import ConfirmationBase, ConfirmationCreate, ConfirmationResponse
from app.schemas.death_register import DeathRegisterBase, DeathRegisterCreate, DeathRegisterResponse
from app.schemas.finances import FinanceBase, FinanceCreate, FinanceResponse, DiocesanContributionUpdate