# ==============================================================================
# app/api/v1/finances.py
# FULL SUPERSET OF THE ORIGINAL RICH LOGIC + PHASE 3 OWNERSHIP/ABAC ENFORCEMENT
# ==============================================================================

from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

# PHASE 3 SECURE IMPORTS
from app.core.security import get_current_user
from app.core.authorization import PermissionChecker, OwnershipService
from app.db.session import get_db
from app.models.all_models import (
    FinanceModel, DiocesanContributionModel, User,
    TransactionType, IncomeCategory, ExpenseCategory,
    DiocesanFundCategory1, DiocesanFundCategory2
)
from app.schemas.schemas import FinanceCreate, DiocesanContributionUpdate

router = APIRouter()

ownership_service = OwnershipService()


# ==============================================================================
# 1. PARISH LEDGER (DAY-TO-DAY TRANSACTIONS)
# ==============================================================================
@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def log_parish_transaction(
    payload: FinanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:write")(current_user)
    await ownership_service.check_ownership(payload, current_user)

    if payload.transaction_type.upper() == "INCOME":
        valid_categories = [e.value for e in IncomeCategory]
        if payload.category not in valid_categories:
            raise HTTPException(status_code=422, detail=f"Invalid Income Category. Must be one of: {valid_categories}")
    elif payload.transaction_type.upper() == "EXPENSE":
        valid_categories = [e.value for e in ExpenseCategory]
        if payload.category not in valid_categories:
            raise HTTPException(status_code=422, detail=f"Invalid Expense Category. Must be one of: {valid_categories}")
    else:
        raise HTTPException(status_code=422, detail="Transaction type must be 'INCOME' or 'EXPENSE'.")

    current_year = payload.transaction_date.year
    query = await db.execute(
        select(func.max(FinanceModel.row_number)).where(
            func.extract('year', FinanceModel.transaction_date) == current_year)
    )
    new_row = (query.scalar() or 0) + 1

    try:
        new_transaction = FinanceModel(
            row_number=new_row,
            transaction_date=payload.transaction_date,
            transaction_type=payload.transaction_type.upper(),
            category=payload.category,
            amount=payload.amount,
            notes=payload.notes,
            recorded_by=current_user.email,
            owner_parish_id=current_user.parish_id,
            owner_deanery_id=current_user.deanery_id,
            owner_user_id=current_user.id
        )
        db.add(new_transaction)
        await db.commit()
        await db.refresh(new_transaction)

        return {"message": "Transaction successfully recorded.", "id": str(new_transaction.id)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


@router.get("/transactions/summary")
async def get_financial_summary(
    year: int = Query(..., description="The reporting year to summarize"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await PermissionChecker("parish:read")(current_user)

    income_query = await db.execute(
        select(func.sum(FinanceModel.amount))
        .where(FinanceModel.transaction_type == "INCOME", func.extract('year', FinanceModel.transaction_date) == year)
    )
    total_income = income_query.scalar() or 0.00

    expense_query = await db.execute(
        select(func.sum(FinanceModel.amount))
        .where(FinanceModel.transaction_type == "EXPENSE", func.extract('year', FinanceModel.transaction_date) == year)
    )
    total_expense = expense_query.scalar() or 0.00

    net_balance = float(total_income) - float(total_expense)

    return {
        "reporting_year": year,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net_balance": net_balance
    }


# ==============================================================================
# 2. DIOCESAN ASSESSMENTS & UMUTULO (BISHOP-ONLY)
# ==============================================================================
@router.post("/diocesan-assessments/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_assessment(
    fund_name: str = Query(..., description="Name of the fund"),
    fund_type: str = Query(..., description="CATEGORY_1_TARGETED or CATEGORY_2_COLLECTION"),
    reporting_year: int = Query(..., description="The year this assessment applies to"),
    target_amount: float = Query(0.00, description="Leave 0 for Category 2 collections"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.office.value != "Bishop":
        raise HTTPException(status_code=403, detail="Only the Bishop can initialize diocesan assessments")

    valid_cat1 = [e.value for e in DiocesanFundCategory1]
    valid_cat2 = [e.value for e in DiocesanFundCategory2]

    if fund_type == "CATEGORY_1_TARGETED" and fund_name not in valid_cat1:
        raise HTTPException(status_code=400, detail=f"Invalid Category 1 Fund. Must be one of: {valid_cat1}")
    if fund_type == "CATEGORY_2_COLLECTION" and fund_name not in valid_cat2:
        raise HTTPException(status_code=400, detail=f"Invalid Category 2 Fund. Must be one of: {valid_cat2}")

    existing = await db.execute(
        select(DiocesanContributionModel)
        .where(DiocesanContributionModel.fund_name == fund_name,
               DiocesanContributionModel.reporting_year == reporting_year)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"{fund_name} has already been initialized for {reporting_year}.")

    variance = -target_amount if fund_type == "CATEGORY_1_TARGETED" else None

    new_assessment = DiocesanContributionModel(
        reporting_year=reporting_year,
        fund_name=fund_name,
        fund_type=fund_type,
        target_amount=target_amount if fund_type == "CATEGORY_1_TARGETED" else None,
        variance_amount=variance,
        owner_parish_id=current_user.parish_id,
        owner_deanery_id=current_user.deanery_id,
        owner_user_id=current_user.id
    )
    db.add(new_assessment)
    await db.commit()

    return {"message": f"{fund_name} initialized for {reporting_year} under Episcopal authority."}