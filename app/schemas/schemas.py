from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Generic, TypeVar
from datetime import date, datetime
import uuid

# ==============================================================================
# BASE GENERIC SCHEMAS
# ==============================================================================
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic schema for returning paginated lists of data."""
    total_count: int
    limit: int
    skip: int
    data: List[T]


# ==============================================================================
# 1. AUTHENTICATION & USERS
# ==============================================================================
class Token(BaseModel):
    access_token: str
    token_type: str


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
    parish_id: Optional[int] = None

    class Config:
        from_attributes = True


# ==============================================================================
# 2. SACRAMENTAL REGISTERS
# ==============================================================================

# --- Baptisms ---
class BaptismBase(BaseModel):
    first_name: str
    last_name: str
    dob: date
    date_of_baptism: date
    place_of_birth: str
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    godparents: str
    minister_of_baptism: str
    village: Optional[str] = None
    center: Optional[str] = None


class BaptismCreate(BaptismBase):
    pass


class BaptismResponse(BaptismBase):
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


# --- First Communions ---
class FirstCommunionBase(BaseModel):
    first_name: str
    last_name: str
    baptism_number: str
    date_of_communion: date
    minister: str
    place_of_baptism: str


class FirstCommunionCreate(FirstCommunionBase):
    pass


class FirstCommunionResponse(FirstCommunionBase):
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


# --- Confirmations ---
class ConfirmationBase(BaseModel):
    first_name: str
    last_name: str
    baptism_number: str
    date_of_confirmation: date
    sponsor_name: str
    minister: str
    place_of_baptism: str


class ConfirmationCreate(ConfirmationBase):
    pass


class ConfirmationResponse(ConfirmationBase):
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


# --- Marriages ---
class MarriageBase(BaseModel):
    husband_first_name: str
    husband_last_name: str
    husband_baptism_number: str
    wife_first_name: str
    wife_last_name: str
    wife_baptism_number: str
    date_of_marriage: date
    witness_1: str
    witness_2: str
    minister: str
    notes: Optional[str] = None


class MarriageCreate(MarriageBase):
    pass


class MarriageResponse(MarriageBase):
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True


# --- Death Register ---
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


class DeathRegisterCreate(DeathRegisterBase):
    pass


class DeathRegisterResponse(DeathRegisterBase):
    id: uuid.UUID
    formatted_number: str

    class Config:
        from_attributes = True


# ==============================================================================
# 3. YOUTH MINISTRY
# ==============================================================================
class YouthProfileBase(BaseModel):
    first_name: str
    last_name: str
    dob: date
    gender: str
    village: str
    center: str
    is_baptised: bool = False
    is_communicant: bool = False


class YouthProfileCreate(YouthProfileBase):
    pass


class YouthProfileResponse(YouthProfileBase):
    id: uuid.UUID

    class Config:
        from_attributes = True


class YouthActionPlanBase(BaseModel):
    academic_year: str
    title: str
    target_demographic: str
    proposed_budget: float
    objectives: str


class YouthActionPlanCreate(YouthActionPlanBase):
    pass


class YouthActionPlanResponse(YouthActionPlanBase):
    id: uuid.UUID
    status: str
    created_by: str
    pp_feedback: Optional[str] = None

    class Config:
        from_attributes = True


# ==============================================================================
# 4. FINANCES & UMUTULO
# ==============================================================================
class DiocesanContributionCreate(BaseModel):
    fund_name: str
    target_amount: Optional[float] = None
    actual_amount: float
    notes: Optional[str] = None