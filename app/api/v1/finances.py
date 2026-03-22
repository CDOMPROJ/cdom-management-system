from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from app.core.dependencies import get_db, get_current_active_user
from app.models.all_models import FinanceModel, ParishModel


# ==========================================
# 1. DATA TRANSFER OBJECTS (SCHEMAS)
# ==========================================
class FinanceCreate(BaseModel):
    transaction_date: date
    transaction_type: str  # Must be 'INCOME' or 'EXPENSE'
    category: str  # e.g., 'Tithe', 'Building Maintenance'
    amount: Decimal
    notes: Optional[str] = None


class FinanceResponse(BaseModel):
    id: str
    transaction_date: date
    transaction_type: str
    category: str
    amount: Decimal
    notes: Optional[str]
    row_number: int

    class Config:
        from_attributes = True


router = APIRouter()


# ==========================================
# 2. LOG PARISH TRANSACTION
# ==========================================
@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(
        finance_in: FinanceCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """
    Records a new income or expense entry into the Parish Ledger.
    Ensures data is saved in the specific Parish Schema.
    """
    if not _current_user.get("parish_id"):
        raise HTTPException(status_code=403, detail="Only Parish accounts can log transactions.")

    # A. ROUTING: Switch database context to the specific Parish Schema
    parish_query = await db.execute(
        select(ParishModel.schema_name).where(ParishModel.id == _current_user["parish_id"])
    )
    schema_name = parish_query.scalar_one_or_none()
    await db.execute(text(f'SET search_path TO "{schema_name}"'))

    # B. SEQUENCE: Get the next row number for this specific ledger
    row_query = await db.execute(select(func.max(FinanceModel.row_number)))
    next_row = (row_query.scalar() or 0) + 1

    # C. PERSISTENCE: Create and save the record
    new_transaction = FinanceModel(
        transaction_date=finance_in.transaction_date,
        transaction_type=finance_in.transaction_type.upper(),
        category=finance_in.category,
        amount=finance_in.amount,
        notes=finance_in.notes,
        row_number=next_row
    )
    db.add(new_transaction)
    await db.commit()

    return {"message": "Transaction recorded.", "transaction_id": new_transaction.id}


# ==========================================
# 3. LEDGER SUMMARY
# ==========================================
@router.get("/summary")
async def get_finance_summary(
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(get_current_active_user)
):
    """Calculates the total income, expenses, and current balance for the parish."""
    # Ensure correct schema
    parish_query = await db.execute(select(ParishModel.schema_name).where(ParishModel.id == _current_user["parish_id"]))
    schema_name = parish_query.scalar_one_or_none()
    await db.execute(text(f'SET search_path TO "{schema_name}"'))

    # Aggregate sums
    income_q = await db.execute(select(func.sum(FinanceModel.amount)).where(FinanceModel.transaction_type == 'INCOME'))
    expense_q = await db.execute(
        select(func.sum(FinanceModel.amount)).where(FinanceModel.transaction_type == 'EXPENSE'))

    total_in = income_q.scalar() or 0
    total_out = expense_q.scalar() or 0

    return {
        "total_income": total_in,
        "total_expenses": total_out,
        "balance": total_in - total_out
    }