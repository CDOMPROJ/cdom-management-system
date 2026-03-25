from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Generic, TypeVar, Dict, Any
from datetime import date, datetime
import uuid
import enum
import re
from pydantic import BaseModel, EmailStr, Field

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
    pass


class BaptismResponse(BaptismBase):
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
    pass


class MarriageResponse(MarriageBase):
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
    pass


class FirstCommunionResponse(FirstCommunionBase):
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
    pass

class ConfirmationResponse(ConfirmationBase):
    id: uuid.UUID
    formatted_number: str # Matches DB column

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
    pass


class DeathRegisterResponse(DeathRegisterBase):
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
    pass

class YouthProfileResponse(YouthProfileBase):
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
    pass


class YouthActionPlanResponse(YouthActionPlanBase):
    id: uuid.UUID
    status: str
    created_by: str
    pp_feedback: Optional[str] = None
    created_at: datetime

    # By including this list, the frontend will automatically receive the
    # entire "Email Thread" history every time it fetches an Action Plan!
    communications: List[CommunicationResponse] = []

    class Config:
        from_attributes = True


# ==============================================================================
# 4. FINANCES & UMUTULO (STRICT NUMERIC GOVERNANCE)
# ==============================================================================
class FinanceBase(BaseModel):
    transaction_date: date
    transaction_type: str  # 'Income' or 'Expense'
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
    pass


class FinanceResponse(FinanceBase):
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
    pass


class PendingActionResponse(PendingActionBase):
    id: uuid.UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True