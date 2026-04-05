from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

# Secure internal imports
from app.core.dependencies import (
    get_db,
    require_create_access,
    require_read_access,
    require_bishop_access  # <-- CANONICAL SECURITY: Only the Bishop sets targets
)
from app.models.all_models import (
    FinanceModel,
    DiocesanContributionModel,
    User,
    TransactionType,
    IncomeCategory,
    ExpenseCategory,
    DiocesanFundCategory1,
    DiocesanFundCategory2
)
from app.schemas.old_schemas import FinanceCreate, DiocesanContributionUpdate

router = APIRouter()


# ==============================================================================
# 1. PARISH LEDGER (DAY-TO-DAY TRANSACTIONS)
# ==============================================================================
@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def log_parish_transaction(
        payload: FinanceCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_create_access)
):
    """
    Logs daily parish income or expenses.
    Strictly validates against the Diocesan Standardized Chart of Accounts.
    """
    # 1. Enforce Standardized Categories
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

    # 2. Sequential Row Generation
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
            recorded_by=current_user.email
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
        _current_user: User = Depends(require_read_access)
):
    """Provides a top-level calculation of Parish Total Income vs Total Expenses."""
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
# 2. DIOCESAN ASSESSMENTS & UMUTULO (EPISCOPAL AUTHORITY ONLY)
# ==============================================================================
@router.post("/diocesan-assessments/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_assessment(
        fund_name: str = Query(..., description="Name of the fund (e.g., Umutulo waku Diocese)"),
        fund_type: str = Query(..., description="CATEGORY_1_TARGETED or CATEGORY_2_COLLECTION"),
        reporting_year: int = Query(..., description="The year this assessment applies to"),
        target_amount: float = Query(0.00, description="Leave 0 for Category 2 collections"),
        db: AsyncSession = Depends(get_db),
        _bishop: User = Depends(require_bishop_access)  # <--- SECURITY: Only the Bishop sets targets!
):
    """
    Initializes a new Diocesan assessment tracker for the year.
    For Category 1 (Targeted), a target amount is required.
    STRICTLY RESTRICTED TO BISHOP/SYSADMIN CLEARANCE.
    """
    # Verify fund names against Enums
    valid_cat1 = [e.value for e in DiocesanFundCategory1]
    valid_cat2 = [e.value for e in DiocesanFundCategory2]

    if fund_type == "CATEGORY_1_TARGETED" and fund_name not in valid_cat1:
        raise HTTPException(status_code=400, detail=f"Invalid Category 1 Fund. Must be one of: {valid_cat1}")
    if fund_type == "CATEGORY_2_COLLECTION" and fund_name not in valid_cat2:
        raise HTTPException(status_code=400, detail=f"Invalid Category 2 Fund. Must be one of: {valid_cat2}")

    # Check if already initialized for this year
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
        variance_amount=variance
    )
    db.add(new_assessment)
    await db.commit()

    return {"message": f"{fund_name} initialized for {reporting_year} under Episcopal authority."}


@router.post("/diocesan-assessments/{assessment_id}/pay", status_code=status.HTTP_200_OK)
async def make_assessment_payment(
        assessment_id: uuid.UUID,
        payload: DiocesanContributionUpdate,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_create_access)  # Priests/Secretaries can PAY, but cannot INITIALIZE
):
    """
    Logs a payment towards a Diocesan assessment and automatically calculates variance (debt).
    Automatically logs a corresponding EXPENSE in the Parish Ledger.
    """
    query = select(DiocesanContributionModel).where(DiocesanContributionModel.id == assessment_id)
    assessment = (await db.execute(query)).scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment record not found.")

    # 1. Update the Actual Amount Paid
    assessment.actual_amount_paid = float(assessment.actual_amount_paid) + payload.payment_amount
    assessment.last_payment_date = payload.payment_date
    if payload.notes:
        assessment.notes = payload.notes

    # 2. Dynamic Variance Math (Only for Category 1)
    if assessment.fund_type == "CATEGORY_1_TARGETED" and assessment.target_amount is not None:
        # Variance = Actual - Target (Negative means we still owe, Positive means surplus)
        assessment.variance_amount = float(assessment.actual_amount_paid) - float(assessment.target_amount)

    await db.commit()

    # Bonus: Automatically log this payment in the standard Parish Ledger as an Expense!
    new_expense = FinanceModel(
        transaction_date=payload.payment_date,
        transaction_type="EXPENSE",
        category="Diocesan Assessment Remittance",
        amount=payload.payment_amount,
        notes=f"Auto-logged payment towards: {assessment.fund_name}",
        recorded_by="SYSTEM_AUTO"
    )
    db.add(new_expense)
    await db.commit()

    return {
        "message": "Payment recorded successfully.",
        "new_total_paid": assessment.actual_amount_paid,
        "current_variance": assessment.variance_amount
    }