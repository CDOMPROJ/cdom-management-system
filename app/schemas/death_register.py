from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import uuid
from app.schemas.schemas import ReligionCategory

class DeathRegisterBase(BaseModel):
    """Base schema for Death Register records."""
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    dob: date
    date_of_death: date
    baptism_number: Optional[str] = None
    cause_of_death: Optional[str] = None
    village: str
    center: str

    @field_validator('dob', 'date_of_death')
    @classmethod
    def dates_cannot_be_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('Date cannot be in the future')
        return v

class DeathRegisterCreate(DeathRegisterBase):
    """Schema used when creating a new death register record."""
    pass

class DeathRegisterResponse(DeathRegisterBase):
    """Response schema for death register records."""
    id: uuid.UUID
    canonical_number: str

    class Config:
        from_attributes = True