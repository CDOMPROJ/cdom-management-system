import io
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from app.core.dependencies import get_db, require_youth_chaplain, require_parish_priest, require_read_access
from app.models.all_models import YouthProfileModel, YouthActionPlanModel, ParishModel
from app.schemas.schemas import YouthProfileCreate, YouthProfileResponse, YouthActionPlanCreate, \
    YouthActionPlanResponse, PaginatedResponse

router = APIRouter()


# ==============================================================================
# HELPER: TENANT ROUTING
# ==============================================================================
async def set_parish_schema(db: AsyncSession, parish_id: int):
    """Securely locks the database context to the specific Parish's schema."""
    if not parish_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a valid parish.")

    parish_query = await db.execute(select(ParishModel.schema_name).where(ParishModel.id == parish_id))
    schema_name = parish_query.scalar_one_or_none()

    if not schema_name:
        raise HTTPException(status_code=404, detail="Parish schema not found.")

    await db.execute(text(f'SET search_path TO "{schema_name}"'))


# ==============================================================================
# 1. YOUTH DEMOGRAPHICS & CATECHUMEN TRACKING (WITH PAGINATION)
# ==============================================================================
@router.post("/profiles", response_model=YouthProfileResponse, status_code=status.HTTP_201_CREATED)
async def register_youth(
        profile_in: YouthProfileCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """Registers a child/youth into the parish system to track their sacramental journey."""
    # A. TENANT ROUTING: Ensure data goes to the parish vault, not the public global schema
    await set_parish_schema(db, _current_user.get("parish_id"))

    new_profile = YouthProfileModel(**profile_in.model_dump())
    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)
    return new_profile


@router.get("/catechumens/pending-baptism", response_model=PaginatedResponse[YouthProfileResponse])
async def get_unbaptised_youth(
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(20, ge=1, le=100, description="Max records to return per page"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """Returns a paginated list of all children/youth registered who have NOT received Baptism."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    # 1. Get the total mathematical count for the frontend to calculate total pages
    count_query = await db.execute(
        select(func.count(YouthProfileModel.id)).where(YouthProfileModel.is_baptised == False)
    )
    total_count = count_query.scalar() or 0

    # 2. Fetch the specific slice of data requested by the mobile app
    query = await db.execute(
        select(YouthProfileModel)
        .where(YouthProfileModel.is_baptised == False)
        .offset(skip)
        .limit(limit)
    )
    records = query.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "skip": skip,
        "data": records
    }


@router.get("/catechumens/pending-communion", response_model=PaginatedResponse[YouthProfileResponse])
async def get_uncommunicated_youth(
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(20, ge=1, le=100, description="Max records to return per page"),
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """Returns a paginated list of youth who are Baptised but waiting for First Communion."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    count_query = await db.execute(
        select(func.count(YouthProfileModel.id))
        .where(YouthProfileModel.is_baptised == True, YouthProfileModel.is_communicant == False)
    )
    total_count = count_query.scalar() or 0

    query = await db.execute(
        select(YouthProfileModel)
        .where(YouthProfileModel.is_baptised == True, YouthProfileModel.is_communicant == False)
        .offset(skip)
        .limit(limit)
    )
    records = query.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "skip": skip,
        "data": records
    }


# ==============================================================================
# 2. ACTION PLAN WORKFLOW (DRAFT -> PP APPROVAL -> DEANERY)
# ==============================================================================
@router.post("/action-plans", response_model=YouthActionPlanResponse, status_code=status.HTTP_201_CREATED)
async def draft_action_plan(
        plan_in: YouthActionPlanCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """YC drafts a new pastoral plan. Starts in DRAFT status."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    new_plan = YouthActionPlanModel(**plan_in.model_dump(), created_by=_current_user.get("email"), status="DRAFT")
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    return new_plan


@router.put("/action-plans/{plan_id}/submit-pp")
async def submit_plan_to_pp(
        plan_id: str,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """YC submits the draft to the Parish Priest for canonical approval."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    plan.status = "PENDING_PP"
    await db.commit()
    return {"message": "Action Plan submitted to Parish Priest for review."}


@router.put("/action-plans/{plan_id}/review")
async def pp_review_plan(
        plan_id: str,
        approved: bool,
        feedback: str = "",
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_parish_priest)
):
    """Parish Priest reviews the plan. Can Approve or Reject with feedback."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    plan.status = "APPROVED_PP" if approved else "DRAFT"
    plan.pp_feedback = feedback
    await db.commit()
    return {"message": f"Plan {'Approved' if approved else 'Rejected'}. Feedback sent to YC."}


@router.put("/action-plans/{plan_id}/submit-deanery")
async def submit_plan_to_deanery(
        plan_id: str,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_youth_chaplain)
):
    """Once approved by PP, the YC forwards the final plan to the Deanery Youth Chaplain."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan or plan.status != "APPROVED_PP":
        raise HTTPException(status_code=400,
                            detail="Plan must be approved by the Parish Priest before submission to Deanery.")

    plan.status = "SUBMITTED_DEANERY"
    await db.commit()
    return {"message": "Official Action Plan successfully submitted to the Deanery Youth Chaplain."}


# ==============================================================================
# 3. GENERATE ACTION PLAN PDF
# ==============================================================================
@router.get("/action-plans/{plan_id}/pdf")
async def generate_plan_pdf(
        plan_id: str,
        db: AsyncSession = Depends(get_db),
        _current_user: dict = Depends(require_read_access)
):
    """Generates a formatted PDF of the Action Plan for physical filing or distribution."""
    await set_parish_schema(db, _current_user.get("parish_id"))

    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 3 * cm, "YOUTH MINISTRY ACTION PLAN")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, height - 4 * cm, f"Academic Year: {plan.academic_year}")
    p.drawCentredString(width / 2, height - 4.5 * cm, f"Status: {plan.status}")

    # Body
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, height - 7 * cm, f"Title: {plan.title}")

    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, height - 8.5 * cm, f"Target Demographic: {plan.target_demographic}")
    p.drawString(2 * cm, height - 9.5 * cm, f"Proposed Budget: ZMW {plan.proposed_budget}")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(2 * cm, height - 11 * cm, "Strategic Objectives:")

    # Text wrapping for objectives
    p.setFont("Helvetica", 11)
    textobject = p.beginText(2 * cm, height - 12 * cm)
    for line in plan.objectives.split('\n'):
        textobject.textLine(line)
    p.drawText(textobject)

    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=YouthPlan_{plan.academic_year}.pdf"
    })