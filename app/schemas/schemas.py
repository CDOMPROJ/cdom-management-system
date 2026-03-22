from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import date, datetime
from typing import Optional, List
import uuid

# Import the Enum directly from models to guarantee database synchronization
from app.models.all_models import ReligionCategory


# ==============================================================================
# GOVERNANCE & APPROVALS
# ==============================================================================
class PendingActionCreate(BaseModel):
    action_type: str = Field(..., examples=["UPDATE"])
    target_table: str = Field(..., examples=["baptisms"])
    target_record_id: str
    proposed_payload: dict


class PendingActionResponse(PendingActionCreate):
    id: uuid.UUID
    requested_by: str
    status: str
    reviewed_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action_type: str = Field(..., description="CREATE, UPDATE, or DELETE")
    target_table: str
    target_record_id: str
    changed_by_email: str
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 1. SECURITY & IDENTITY (PUBLIC SCHEMA)
# ==============================================================================
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    role: str = Field(..., description="E.g., Parish Secretary, Parish Priest, SysAdmin")
    office: Optional[str] = None
    parish_id: Optional[int] = None
    deanery_id: Optional[int] = None


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. PARISH & DEANERY (PUBLIC SCHEMA)
# ==============================================================================
class ParishBase(BaseModel):
    name: str
    deanery_id: int
    schema_name: str


class ParishResponse(ParishBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. SACRAMENTAL REGISTERS (BRONZE LAYER)
# ==============================================================================

# --- BAPTISMS ---
class BaptismBase(BaseModel):
    first_name: str = Field(..., examples=["Peter"])
    middle_name: Optional[str] = None
    last_name: str = Field(..., examples=["Mulenga"])
    dob: date = Field(..., description="Required for statistical age bracketing")
    date_of_baptism: date
    minister_of_baptism: str
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    godparents: str
    village: str
    center: str


class BaptismCreate(BaptismBase):
    pass


class BaptismResponse(BaptismBase):
    id: uuid.UUID
    formatted_number: str
    registry_year: int
    is_deceased: bool
    model_config = ConfigDict(from_attributes=True)


# --- FIRST COMMUNIONS ---
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


class FirstCommunionCreate(FirstCommunionBase):
    pass


class FirstCommunionResponse(FirstCommunionBase):
    id: uuid.UUID
    formatted_number: str
    registry_year: int
    model_config = ConfigDict(from_attributes=True)


# --- CONFIRMATIONS ---
class ConfirmationBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date = Field(..., description="Required for statistical age bracketing (Adult vs Child)")
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


class ConfirmationCreate(ConfirmationBase):
    pass


class ConfirmationResponse(ConfirmationBase):
    id: uuid.UUID
    formatted_number: str
    registry_year: int
    model_config = ConfigDict(from_attributes=True)


# --- MARRIAGES (CANON LAW ENFORCED) ---
class MarriageBase(BaseModel):
    # Groom Details
    groom_first_name: str = Field(..., examples=["John"])
    groom_middle_name: Optional[str] = None
    groom_last_name: str = Field(..., examples=["Mulenga"])
    groom_father_first_name: str
    groom_father_last_name: str
    groom_mother_first_name: str
    groom_mother_last_name: str
    groom_dob: date
    groom_baptised_at: str
    groom_baptism_number: str
    groom_religion_category: ReligionCategory = Field(default=ReligionCategory.CATHOLIC)
    groom_religion_specific: Optional[str] = Field(None, examples=["UCZ"])

    # Bride Details
    bride_first_name: str = Field(..., examples=["Mary"])
    bride_middle_name: Optional[str] = None
    bride_last_name: str = Field(..., examples=["Bwalya"])
    bride_father_first_name: str
    bride_father_last_name: str
    bride_mother_first_name: str
    bride_mother_last_name: str
    bride_dob: date
    bride_baptised_at: str
    bride_baptism_number: str
    bride_religion_category: ReligionCategory = Field(default=ReligionCategory.CATHOLIC)
    bride_religion_specific: Optional[str] = Field(None, examples=["SDA"])

    # Event Details
    marriage_date: date
    place_of_marriage: str
    minister: str
    witness_1: str
    witness_2: str
    banns_published_on: Optional[date] = None
    dispensation_from_impediment: Optional[str] = None


class MarriageCreate(MarriageBase):
    pass


class MarriageResponse(MarriageBase):
    id: uuid.UUID
    formatted_number: str
    registry_year: int
    model_config = ConfigDict(from_attributes=True)


# --- DEATH REGISTER ---
class DeathRegisterBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    baptism_number: Optional[str] = None
    date_of_death: date
    date_of_burial: date
    place_of_burial: str
    minister_of_rites: str
    received_last_rites: bool = False


class DeathRegisterCreate(DeathRegisterBase):
    pass


class DeathRegisterResponse(DeathRegisterBase):
    id: uuid.UUID
    formatted_number: str
    registry_year: int
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. GOLD LAYER (BISHOP'S DASHBOARD & CENSUS)
# ==============================================================================
class AnnualParishCensusBase(BaseModel):
    """Payload for submitting the Annual Statistics report data."""
    reporting_year: int
    catechumens_count: int = Field(0, ge=0)
    converts_without_conditional_baptism: int = Field(0, ge=0)
    paid_catechists: int = Field(0, ge=0)
    voluntary_catechists: int = Field(0, ge=0)
    total_catholic_population: int = Field(0, ge=0)
    other_christians: int = Field(0, ge=0)
    non_christians: int = Field(0, ge=0)


class AnnualParishCensusCreate(AnnualParishCensusBase):
    parish_id: int  # Often injected by the router via JWT, but required for the DB


class AnnualParishCensusResponse(AnnualParishCensusBase):
    id: int
    parish_id: int
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. GLOBAL SEARCH RESULTS
# ==============================================================================
class GlobalSearchResult(BaseModel):
    name: str
    canonical: str
    parish: str
    type: str


class SearchResponse(BaseModel):
    scope: str
    message: str
    results: List[GlobalSearchResult]


from decimal import Decimal

# ==============================================================================
# 6. FINANCIAL LEDGERS (PARISH SCHEMA)
# ==============================================================================
class FinanceBase(BaseModel):
    transaction_date: date
    transaction_type: str
    category: str
    amount: Decimal
    notes: Optional[str] = None

class FinanceCreate(FinanceBase):
    pass

class FinanceResponse(FinanceBase):
    id: uuid.UUID
    row_number: int
    model_config = ConfigDict(from_attributes=True)


class DiocesanContributionBase(BaseModel):
    reporting_year: int
    fund_name: str
    target_amount: Optional[Decimal] = None
    actual_amount: Decimal = Field(default=0.00)
    variance_amount: Optional[Decimal] = None
    notes: Optional[str] = None

class DiocesanContributionCreate(DiocesanContributionBase):
    pass

class DiocesanContributionResponse(DiocesanContributionBase):
    id: uuid.UUID
    row_number: int
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. YOUTH MINISTRY & CATECHESIS (PARISH SCHEMA)
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

class YouthProfileCreate(YouthProfileBase):
    pass

class YouthProfileResponse(YouthProfileBase):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class YouthActionPlanBase(BaseModel):
    academic_year: int
    title: str
    objectives: str
    target_demographic: str
    proposed_budget: Decimal = Field(default=0.00)
    status: str = "DRAFT"
    pp_feedback: Optional[str] = None

class YouthActionPlanCreate(YouthActionPlanBase):
    pass

class YouthActionPlanResponse(YouthActionPlanBase):
    id: uuid.UUID
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)