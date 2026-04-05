from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import uuid
from app.schemas.schemas import ReligionCategory

class BaptismBase(BaseModel):
    """Base schema for Baptism records."""
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

class BaptismCreate(BaseModel):
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