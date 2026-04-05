from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import uuid
from app.schemas.schemas import ReligionCategory

class MarriageBase(BaseModel):
    """Base schema for Marriage records."""
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
    pass

class MarriageResponse(MarriageBase):
    """Response schema for marriage records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True