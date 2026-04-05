import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from rapidfuzz import process
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from app.core.dependencies import get_db, require_create_access, require_read_access, require_update_access, \
    require_parish_priest
from app.models.all_models import YouthProfileModel, YouthActionPlanModel, ActionPlanCommunicationModel, User
from app.schemas.old_schemas import YouthProfileCreate, YouthProfileResponse, YouthActionPlanCreate, \
    YouthActionPlanResponse, PaginatedResponse

# If you have your email system hooked up, import it here:
# from app.core.email import send_system_email

router = APIRouter()


# ==============================================================================
# HELPER: COMMUNICATION LOGGER
# ==============================================================================
async def log_communication(
        db: AsyncSession, plan_id: uuid.UUID, sender: User, recipient_email: str,
        recipient_role: str, action: str, comments: str = ""
):
    """Automatically writes to the audit ledger and can trigger Resend emails."""
    comm = ActionPlanCommunicationModel(
        plan_id=plan_id,
        sender_email=sender.email,
        sender_role=sender.role,
        recipient_email=recipient_email,
        recipient_role=recipient_role,
        action_taken=action,
        comments=comments
    )
    db.add(comm)

    # Optional: Trigger real email
    # send_system_email(recipient_email, f"Action Plan Update: {action}", f"<p>{comments}</p>")


# ==============================================================================
# 1. YOUTH PROFILES & CATECHUMEN TRACKING
# ==============================================================================
@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def register_youth(
        profile_in: YouthProfileCreate,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_create_access)
):
    try:
        new_profile = YouthProfileModel(**profile_in.model_dump())
        db.add(new_profile)
        await db.commit()
        return {"message": "Youth profile created.", "id": str(new_profile.id)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


@router.get("/profiles/search")
async def search_youth_profiles(
        q: str = Query(..., min_length=2),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    result = await db.execute(select(YouthProfileModel))
    rows = result.scalars().all()
    if not rows: return {"results": [], "message": "No youth profiles found."}

    search_strings, record_map = [], []
    for record in rows:
        search_data = f"{record.first_name} {record.last_name} {record.parent_guardian_name}".lower()
        search_strings.append(search_data)
        record_map.append(record)

    matches = process.extract(q.lower(), search_strings, limit=10, score_cutoff=60.0)
    return {"query": q, "match_count": len(matches), "results": [record_map[idx] for _, _, idx in matches]}


@router.get("/catechumens/pending-baptism", response_model=PaginatedResponse[YouthProfileResponse])
async def get_unbaptised_youth(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    count_query = await db.execute(
        select(func.count(YouthProfileModel.id)).where(YouthProfileModel.is_baptised == False))
    total_count = count_query.scalar() or 0

    query = await db.execute(
        select(YouthProfileModel).where(YouthProfileModel.is_baptised == False).offset(skip).limit(limit))
    return {"total_count": total_count, "limit": limit, "skip": skip, "data": query.scalars().all()}


@router.get("/catechumens/pending-communion", response_model=PaginatedResponse[YouthProfileResponse])
async def get_uncommunicated_youth(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    count_query = await db.execute(select(func.count(YouthProfileModel.id)).where(YouthProfileModel.is_baptised == True,
                                                                                  YouthProfileModel.is_communicant == False))
    total_count = count_query.scalar() or 0

    query = await db.execute(select(YouthProfileModel).where(YouthProfileModel.is_baptised == True,
                                                             YouthProfileModel.is_communicant == False).offset(
        skip).limit(limit))
    return {"total_count": total_count, "limit": limit, "skip": skip, "data": query.scalars().all()}


# ==============================================================================
# 2. ACTION PLAN WORKFLOW (HIERARCHICAL STATE MACHINE)
# ==============================================================================
@router.post("/action-plans", response_model=YouthActionPlanResponse, status_code=status.HTTP_201_CREATED)
async def draft_action_plan(
        plan_in: YouthActionPlanCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_create_access)  # YC Level
):
    """YC drafts a new pastoral plan. Starts in DRAFT status."""
    new_plan = YouthActionPlanModel(**plan_in.model_dump(), created_by=current_user.email, status="DRAFT")
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    return new_plan


@router.get("/action-plans", response_model=list[YouthActionPlanResponse])
async def get_all_action_plans(
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    """Fetches plans and eagerly loads the communication email threads."""
    query = select(YouthActionPlanModel).options(selectinload(YouthActionPlanModel.communications)).order_by(
        YouthActionPlanModel.academic_year.desc())
    return (await db.execute(query)).scalars().all()


@router.put("/action-plans/{plan_id}/submit-pp")
async def submit_plan_to_pp(
        plan_id: uuid.UUID,
        pp_email: str = Query(..., description="The official email of the Parish Priest"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)  # YC Level
):
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan: raise HTTPException(status_code=404, detail="Plan not found.")

    plan.status = "PENDING_PP"
    await log_communication(db, plan_id, current_user, pp_email, "Parish Priest", "SUBMITTED_FOR_REVIEW",
                            "Please review the proposed youth budget.")
    await db.commit()
    return {"message": "Plan submitted to Parish Priest."}


@router.put("/action-plans/{plan_id}/review-pp")
async def pp_review_plan(
        plan_id: uuid.UUID,
        approved: bool,
        feedback: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_parish_priest)  # MUST be Boss
):
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan or plan.status != "PENDING_PP": raise HTTPException(status_code=400,
                                                                    detail="Plan not ready for PP review.")

    plan.status = "APPROVED_PP" if approved else "DRAFT"
    plan.pp_feedback = feedback

    await log_communication(db, plan_id, current_user, plan.created_by, "Youth Chaplain",
                            f"PP_{'APPROVED' if approved else 'REJECTED'}", feedback)
    await db.commit()
    return {"message": "PP Review completed."}


@router.put("/action-plans/{plan_id}/submit-dyc")
async def submit_plan_to_dyc(
        plan_id: uuid.UUID,
        dyc_email: str = Query(..., description="The official email of the Deanery Youth Chaplain"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)
):
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan or plan.status != "APPROVED_PP": raise HTTPException(status_code=400,
                                                                     detail="Must be approved by PP first.")

    plan.status = "PENDING_DYC"
    await log_communication(db, plan_id, current_user, dyc_email, "Deanery Youth Chaplain", "SUBMITTED_TO_DEANERY",
                            "Forwarding Parish Plan for Deanery consolidation.")
    await db.commit()
    return {"message": "Plan submitted to DYC."}


@router.put("/action-plans/{plan_id}/review-dyc")
async def dyc_review_plan(
        plan_id: uuid.UUID,
        approved: bool,
        feedback: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)  # DYC Level
):
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan or plan.status != "PENDING_DYC": raise HTTPException(status_code=400,
                                                                     detail="Plan not ready for DYC review.")

    plan.status = "APPROVED_DYC" if approved else "REJECTED_BY_DYC"
    await log_communication(db, plan_id, current_user, plan.created_by, "Youth Chaplain",
                            f"DYC_{'APPROVED' if approved else 'REJECTED'}", feedback)
    await db.commit()
    return {"message": "DYC Review completed."}


@router.put("/action-plans/{plan_id}/submit-dean")
async def submit_plan_to_dean(
        plan_id: uuid.UUID,
        dean_email: str = Query(..., description="The official email of the Dean"),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_update_access)  # DYC forwards to Dean
):
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan or plan.status != "APPROVED_DYC": raise HTTPException(status_code=400,
                                                                      detail="Must be approved by DYC first.")

    plan.status = "PENDING_DEAN"
    await log_communication(db, plan_id, current_user, dean_email, "Dean", "SUBMITTED_TO_DEAN",
                            "Forwarding for final Deanery approval.")
    await db.commit()
    return {"message": "Plan submitted to Dean."}


# ==============================================================================
# 3. GENERATE ACTION PLAN PDF
# ==============================================================================
@router.get("/action-plans/{plan_id}/pdf")
async def generate_plan_pdf(
        plan_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    """Generates a formatted PDF of the Action Plan for physical filing."""
    plan = (
        await db.execute(select(YouthActionPlanModel).where(YouthActionPlanModel.id == plan_id))).scalar_one_or_none()
    if not plan: raise HTTPException(status_code=404, detail="Plan not found.")

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