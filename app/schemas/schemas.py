# ==========================================
# CDOM Pastoral Management System – Schemas
# FINAL MERGED & OPTIMIZED VERSION
# Single source of truth for all FastAPI endpoints
# ==========================================

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Generic, TypeVar, Dict, Any
from datetime import date, datetime
import uuid
import enum
import re

T = TypeVar("T")

# ==========================================
# 1. COMMON / SHARED SCHEMAS
# ==========================================
class PaginatedResponse(BaseModel, Generic[T]):
    total_count: int
    limit: int
    skip: int
    data: List[T]


class ErrorResponse(BaseModel):
    """Standardized error response used across all endpoints."""
    detail: str
    code: str = "error"
    timestamp: Optional[str] = None


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
    """Schema used when creating a new deanery."""
    name: str

class DeaneryResponse(DeaneryBase):
    id: int

    class Config:
        from_attributes = True

class ParishBase(BaseModel):
    name: str
    deanery_id: int
    schema_name: str

class ParishCreate(ParishBase):
    """Schema used when creating a new parish."""
    name: str
    deanery_id: int
    schema_name: str

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
    """Dynamically returns either a full JWT, or demands MFA with a temp token."""
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
    """Payload submitted by the user to finalize account. Enforces password security."""
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


# ==============================================================================
# 2. SACRAMENTAL REGISTERS (WITH DATE GOVERNANCE)
# ==============================================================================
class BaptismBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    date_of_baptism: date
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    godparents: str
    minister_of_baptism: str
    village: str
    center: str

    @field_validator('dob', 'date_of_baptism')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v


class BaptismCreate(BaptismBase):
    """Schema used when creating a new baptism record."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    date_of_baptism: date
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    godparents: str
    minister_of_baptism: str
    village: str
    center: str


class BaptismResponse(BaptismBase):
    """Response schema for baptism records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


class MarriageBase(BaseModel):
    groom_first_name: str
    groom_last_name: str
    groom_dob: date
    groom_religion: ReligionCategory
    groom_baptism_number: Optional[str] = None
    groom_diocese_of_baptism: Optional[str] = None
    groom_parish_of_baptism: Optional[str] = None
    groom_christian_denomination: Optional[str] = None
    groom_non_christian_religion: Optional[str] = None

    bride_first_name: str
    bride_last_name: str
    bride_dob: date
    bride_religion: ReligionCategory
    bride_baptism_number: Optional[str] = None
    bride_diocese_of_baptism: Optional[str] = None
    bride_parish_of_baptism: Optional[str] = None
    bride_christian_denomination: Optional[str] = None
    bride_non_christian_religion: Optional[str] = None

    marriage_date: date
    center: Optional[str] = None
    minister: str
    witness_1: str
    witness_2: str
    notes: Optional[str] = None
    banns_published_on: Optional[date] = None
    dispensation_from_impediment: Optional[str] = None

    @field_validator('groom_dob', 'bride_dob', 'marriage_date', 'banns_published_on')
    @classmethod
    def dates_cannot_be_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError('Date cannot be in the future')
        return v


class MarriageCreate(MarriageBase):
    """Schema used when creating a new marriage record."""
    groom_first_name: str
    groom_last_name: str
    groom_dob: date
    groom_religion: ReligionCategory
    groom_baptism_number: Optional[str] = None
    groom_diocese_of_baptism: Optional[str] = None
    groom_parish_of_baptism: Optional[str] = None
    groom_christian_denomination: Optional[str] = None
    groom_non_christian_religion: Optional[str] = None

    bride_first_name: str
    bride_last_name: str
    bride_dob: date
    bride_religion: ReligionCategory
    bride_baptism_number: Optional[str] = None
    bride_diocese_of_baptism: Optional[str] = None
    bride_parish_of_baptism: Optional[str] = None
    bride_christian_denomination: Optional[str] = None
    bride_non_christian_religion: Optional[str] = None

    marriage_date: date
    center: Optional[str] = None
    minister: str
    witness_1: str
    witness_2: str
    notes: Optional[str] = None
    banns_published_on: Optional[date] = None
    dispensation_from_impediment: Optional[str] = None


class MarriageResponse(MarriageBase):
    """Response schema for marriage records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


class FirstCommunionBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    baptism_number: str
    baptised_at: str
    communion_date: date
    minister: str
    place_of_communion: str

    @field_validator('communion_date')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v


class FirstCommunionCreate(FirstCommunionBase):
    """Schema used when creating a new first communion record."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    baptism_number: str
    baptised_at: str
    communion_date: date
    minister: str
    place_of_communion: str


class FirstCommunionResponse(FirstCommunionBase):
    """Response schema for first communion records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


class ConfirmationBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    baptism_number: str
    baptised_at: str
    confirmation_date: date
    minister: str
    place_of_confirmation: str
    god_parent: str
    god_parent_is_baptised: bool
    god_parent_is_confirmed: bool

    @field_validator('dob', 'confirmation_date')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v

class ConfirmationCreate(ConfirmationBase):
    """Schema used when creating a new confirmation record."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    baptism_number: str
    baptised_at: str
    confirmation_date: date
    minister: str
    place_of_confirmation: str
    god_parent: str
    god_parent_is_baptised: bool
    god_parent_is_confirmed: bool

class ConfirmationResponse(ConfirmationBase):
    """Response schema for confirmation records."""
    id: uuid.UUID
    formatted_number: str

    class Config:
        from_attributes = True


class DeathRegisterBase(BaseModel):
    first_name: str
    last_name: str
    date_of_death: date
    date_of_burial: date
    place_of_burial: str
    cause_of_death: Optional[str] = None
    sacraments_received: Optional[str] = None
    minister: str
    baptism_number: Optional[str] = None
    next_of_kin: str

    @field_validator('date_of_death', 'date_of_burial')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v


class DeathRegisterCreate(DeathRegisterBase):
    """Schema used when creating a new death register record."""
    first_name: str
    last_name: str
    date_of_death: date
    date_of_burial: date
    place_of_burial: str
    cause_of_death: Optional[str] = None
    sacraments_received: Optional[str] = None
    minister: str
    baptism_number: Optional[str] = None
    next_of_kin: str


class DeathRegisterResponse(DeathRegisterBase):
    """Response schema for death register records."""
    id: uuid.UUID
    formatted_number: str

    class Config:
        from_attributes = True


# ==============================================================================
# 3. YOUTH MINISTRY & CHILD ANIMATION
# ==============================================================================
class YouthProfileBase(BaseModel):
    first_name: str
    last_name: str
    dob: date
    parent_guardian_name: str
    contact_number: Optional[str] = None
    village_center: str
    is_baptised: bool = False
    is_communicant: bool = False
    is_confirmed: bool = False
    canonical_baptism_number: Optional[str] = None

    @field_validator('dob')
    @classmethod
    def dob_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date of birth cannot be in the future')
        return v

class YouthProfileCreate(YouthProfileBase):
    """Schema used when creating a new youth profile."""
    first_name: str
    last_name: str
    dob: date
    parent_guardian_name: str
    contact_number: Optional[str] = None
    village_center: str
    is_baptised: bool = False
    is_communicant: bool = False
    is_confirmed: bool = False
    canonical_baptism_number: Optional[str] = None

class YouthProfileResponse(YouthProfileBase):
    """Response schema for youth profiles."""
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class CommunicationBase(BaseModel):
    sender_email: str
    sender_role: str
    recipient_email: str
    recipient_role: str
    action_taken: str
    comments: Optional[str] = None


class CommunicationResponse(CommunicationBase):
    """Response schema for action plan communications."""
    id: uuid.UUID
    plan_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class YouthActionPlanBase(BaseModel):
    academic_year: int
    title: str
    target_demographic: str
    proposed_budget: float = Field(..., ge=0.0, description="Budget cannot be negative")
    objectives: str


class YouthActionPlanCreate(YouthActionPlanBase):
    """Schema used when creating a new youth action plan."""
    academic_year: int
    title: str
    target_demographic: str
    proposed_budget: float = Field(..., ge=0.0, description="Budget cannot be negative")
    objectives: str


class YouthActionPlanResponse(YouthActionPlanBase):
    """Response schema for youth action plans."""
    id: uuid.UUID
    status: str
    created_by: str
    pp_feedback: Optional[str] = None
    created_at: datetime

    communications: List[CommunicationResponse] = []

    class Config:
        from_attributes = True


# ==============================================================================
# 4. FINANCES & UMUTULO (STRICT NUMERIC GOVERNANCE)
# ==============================================================================
class FinanceBase(BaseModel):
    transaction_date: date
    transaction_type: str
    category: str
    amount: float = Field(..., gt=0.0, description="Amount must be greater than zero")
    notes: Optional[str] = None

    @field_validator('transaction_date')
    @classmethod
    def date_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Transaction date cannot be in the future')
        return v


class FinanceCreate(FinanceBase):
    """Schema used when creating a new financial transaction."""
    transaction_date: date
    transaction_type: str
    category: str
    amount: float = Field(..., gt=0.0, description="Amount must be greater than zero")
    notes: Optional[str] = None


class FinanceResponse(FinanceBase):
    """Response schema for finance records."""
    id: uuid.UUID
    recorded_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class DiocesanContributionUpdate(BaseModel):
    """Used when the parish makes a payment towards their assessment."""
    payment_amount: float = Field(..., gt=0.0)
    payment_date: date
    notes: Optional[str] = None


class DiocesanContributionResponse(BaseModel):
    """Response schema for diocesan contribution records."""
    id: uuid.UUID
    reporting_year: int
    fund_name: str
    fund_type: str
    target_amount: Optional[float]
    actual_amount_paid: float
    variance_amount: Optional[float]
    last_payment_date: Optional[date]

    class Config:
        from_attributes = True


# ==========================================
# 5. CLERGY REGISTRY SCHEMAS
# ==========================================
class ClergyRegistryBase(BaseModel):
    category: str
    congregation: Optional[str] = None
    status: str
    current_location: Optional[str] = None
    ministry_category: Optional[str] = None

class ClergyRegistryCreate(ClergyRegistryBase):
    """Schema used when creating a new clergy registry record."""

class ClergyRegistryResponse(ClergyRegistryBase):
    id: uuid.UUID
    last_updated: datetime
    updated_by: str

    class Config:
        from_attributes = True


# ==============================================================================
# 5. GLOBAL SEARCH (RAPIDFUZZ)
# ==============================================================================
class GlobalSearchResult(BaseModel):
    record_type: str
    canonical_number: Optional[str] = None
    first_name: str
    last_name: str
    date: date
    parish_id: int
    parish_name: str
    match_score: float


class SearchResponse(BaseModel):
    query: str
    results: List[GlobalSearchResult]


# ==============================================================================
# 6. GOVERNANCE & APPROVALS (PENDING ACTIONS)
# ==============================================================================
class PendingActionBase(BaseModel):
    requested_by: EmailStr
    action_type: str
    target_table: str
    target_record_id: str
    proposed_payload: Dict[str, Any]


class PendingActionCreate(PendingActionBase):
    """Schema used when creating a new pending action."""
    requested_by: EmailStr
    action_type: str
    target_table: str
    target_record_id: str
    proposed_payload: Dict[str, Any]


class PendingActionResponse(PendingActionBase):
    """Response schema for pending actions."""
    id: uuid.UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# SECURITYPATCH ADDITIONS
# ==========================================
class Token(BaseModel):
    """Response schema for access + refresh tokens (SecurityPatch)."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    """Request schema for refreshing tokens (SecurityPatch)."""
    refresh_token: str

class PasswordChangeRequest(BaseModel):
    """Request schema for changing password (SecurityPatch)."""
    new_password: str