from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid

class FinanceBase(BaseModel):
    """Base schema for Finance / Transaction records."""
    transaction_date: date
    transaction_type: str
    category: str
    amount: float
    notes: Optional[str] = None

class FinanceCreate(FinanceBase):
    """Schema used when creating a new financial transaction."""
    pass

class FinanceResponse(FinanceBase):
    """Response schema for finance records."""
    id: uuid.UUID
    row_number: int

    class Config:
        from_attributes = True

class DiocesanContributionUpdate(BaseModel):
    """Schema for updating diocesan contribution payments."""
    payment_amount: float
    payment_date: date
    notes: Optional[str] = None