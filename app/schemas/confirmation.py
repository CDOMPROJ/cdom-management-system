from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import uuid
from app.schemas.schemas import ReligionCategory

class ConfirmationBase(BaseModel):
    """Base schema for Confirmation records."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    father_first_name: str
    father_last_name: str
    mother_first_name: str
    mother_last_name: str
    baptism_number: str
    confirmation_date: date
    minister: str
    place_of_confirmation: str

    @field_validator('confirmation_date', 'dob')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v

class ConfirmationCreate(ConfirmationBase):
    """Schema used when creating a new confirmation record."""
    pass

class ConfirmationResponse(ConfirmationBase):
    """Response schema for confirmation records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True