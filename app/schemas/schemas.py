# ==========================================
# CDOM Pastoral Management System – Schemas
# FINAL MERGED & OPTIMIZED VERSION
# Single source of truth for all FastAPI endpoints
# ==========================================

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List, Generic, TypeVar, Dict, Any
from datetime import date, datetime
import uuid
import enum
import re

# FastAPI Dependency Injection imports
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

T = TypeVar("T")

# OAuth2 integration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ==========================================
# 1. COMMON / SHARED SCHEMAS
# ==========================================
class PaginatedResponse(BaseModel, Generic[T]):
    total_count: int
    limit: int
    skip: int
    data: List[T]

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
    timestamp: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


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
    name: str

class DeaneryResponse(DeaneryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ParishBase(BaseModel):
    name: str
    deanery_id: int
    schema_name: str

class ParishCreate(ParishBase):
    name: str
    deanery_id: int
    schema_name: str

class ParishResponse(ParishBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 1. AUTHENTICATION SCHEMAS – OPTIMIZED & GROUPED
# ==============================================================================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    username: Optional[str] = None

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
        if len(v) < 16:
            raise ValueError('Password must be at least 16 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one number')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError('Password must contain at least one special character')
        return v

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
    model_config = ConfigDict(from_attributes=True)

class DirectUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=16)
    role: str
    office: str
    parish_id: int | None = None
    deanery_id: int | None = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=16)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=16)

class WebAuthnRegistrationRequest(BaseModel):
    credential_id: str
    public_key: str
    attestation_object: str
    client_data_json: str

class WebAuthnLoginRequest(BaseModel):
    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str

class PasswordPolicyResponse(BaseModel):
    min_length: int = 16
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    password_history: int = 12
    expiry_days: int = 90

class AccountLockoutStatus(BaseModel):
    locked: bool
    remaining_attempts: int
    lockout_until: Optional[datetime] = None

class PhoneVerificationRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?1?\d{9,15}$")

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+?1?\d{9,15}$", v):
            raise ValueError('Invalid phone number format')
        return v

class PhoneVerificationCode(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


# ==============================================================================
# 2. SACRAMENTAL REGISTERS (WITH ENHANCED PYDANTIC V2 VALIDATORS)
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
    id: uuid.UUID
    canonical_number: str
    model_config = ConfigDict(from_attributes=True)


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
    id: uuid.UUID
    canonical_number: str
    model_config = ConfigDict(from_attributes=True)


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
    id: uuid.UUID
    canonical_number: str
    model_config = ConfigDict(from_attributes=True)


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
    id: uuid.UUID
    formatted_number: str
    model_config = ConfigDict(from_attributes=True)


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
    id: uuid.UUID
    formatted_number: str
    model_config = ConfigDict(from_attributes=True)


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
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CommunicationBase(BaseModel):
    sender_email: str
    sender_role: str
    recipient_email: str
    recipient_role: str
    action_taken: str
    comments: Optional[str] = None


class CommunicationResponse(CommunicationBase):
    id: uuid.UUID
    plan_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class YouthActionPlanBase(BaseModel):
    academic_year: int
    title: str
    target_demographic: str
    proposed_budget: float = Field(..., ge=0.0, description="Budget cannot be negative")
    objectives: str


class YouthActionPlanCreate(YouthActionPlanBase):
    academic_year: int
    title: str
    target_demographic: str
    proposed_budget: float = Field(..., ge=0.0, description="Budget cannot be negative")
    objectives: str


class YouthActionPlanResponse(YouthActionPlanBase):
    id: uuid.UUID
    status: str
    created_by: str
    pp_feedback: Optional[str] = None
    created_at: datetime
    communications: List[CommunicationResponse] = []
    model_config = ConfigDict(from_attributes=True)


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
    transaction_date: date
    transaction_type: str
    category: str
    amount: float = Field(..., gt=0.0, description="Amount must be greater than zero")
    notes: Optional[str] = None

class FinanceResponse(FinanceBase):
    id: uuid.UUID
    recorded_by: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DiocesanContributionUpdate(BaseModel):
    payment_amount: float = Field(..., gt=0.0)
    payment_date: date
    notes: Optional[str] = None


class DiocesanContributionResponse(BaseModel):
    id: uuid.UUID
    reporting_year: int
    fund_name: str
    fund_type: str
    target_amount: Optional[float]
    actual_amount_paid: float
    variance_amount: Optional[float]
    last_payment_date: Optional[date]
    model_config = ConfigDict(from_attributes=True)


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
    category: str
    congregation: Optional[str] = None
    status: str
    current_location: Optional[str] = None
    ministry_category: Optional[str] = None


class ClergyRegistryResponse(ClergyRegistryBase):
    id: uuid.UUID
    last_updated: datetime
    updated_by: str
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. GLOBAL SEARCH (RAPIDFUZZ)
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
# 7. GOVERNANCE & APPROVALS (PENDING ACTIONS)
# ==============================================================================
class PendingActionBase(BaseModel):
    requested_by: EmailStr
    action_type: str
    target_table: str
    target_record_id: str
    proposed_payload: Dict[str, Any]


class PendingActionCreate(PendingActionBase):
    requested_by: EmailStr
    action_type: str
    target_table: str
    target_record_id: str
    proposed_payload: Dict[str, Any]


class PendingActionResponse(PendingActionBase):
    id: uuid.UUID
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# END OF SCHEMAS
# ==============================================================================