from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid

class FinanceBase(BaseModel):
    transaction_date: date
    transaction_type: str
    category: str
    amount: float
    notes: Optional[str] = None

class FinanceCreate(FinanceBase):
    pass

class FinanceResponse(FinanceBase):
    id: uuid.UUID
    row_number: int

    class Config:
        from_attributes = True

class DiocesanContributionUpdate(BaseModel):
    payment_amount: float
    payment_date: date
    notes: Optional[str] = None