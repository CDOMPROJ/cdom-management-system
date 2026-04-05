from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import uuid
from app.schemas.schemas import ReligionCategory

class FirstCommunionBase(BaseModel):
    """Base schema for First Communion records."""
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
    pass

class FirstCommunionResponse(FirstCommunionBase):
    """Response schema for first communion records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True