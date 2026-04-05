from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

# Secure internal imports
from app.core.dependencies import get_db, require_sysadmin_access, require_read_access, get_current_active_user
from app.models.all_models import DeaneryModel, ParishModel, DiocesanAnalyticsModel, User
from app.schemas.old_schemas import DeaneryCreate, DeaneryResponse, ParishCreate, ParishResponse

router = APIRouter()


# ==============================================================================
# HELPER: DEANERY SECURITY & AUTHENTICATION
# ==============================================================================
def verify_deanery_role(current_user: User = Depends(get_current_active_user)):
    """Ensures only a Dean, Bishop, or SysAdmin can view specific deanery analytics."""
    allowed_roles = ["Dean", "Bishop", "SysAdmin"]

    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Executive or Deanery-level access required.")

    # If the user is a Dean, ensure they actually have a deanery assigned
    if current_user.role == "Dean" and not current_user.deanery_id:
        raise HTTPException(status_code=400, detail="Dean account is not linked to a valid Deanery.")

    return current_user


# ==============================================================================
# 1. PROVISIONING: CREATE & LIST DEANERIES (SYSADMIN)
# ==============================================================================
@router.post("/", response_model=DeaneryResponse, status_code=status.HTTP_201_CREATED)
async def create_deanery(
        payload: DeaneryCreate,
        db: AsyncSession = Depends(get_db),
        _admin: User = Depends(require_sysadmin_access)  # SECURITY: Only SysAdmins/Bishop
):
    """Registers a new Deanery region in the Diocese."""
    query = select(DeaneryModel).where(DeaneryModel.name == payload.name)
    existing = (await db.execute(query)).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="A Deanery with this name already exists.")

    new_deanery = DeaneryModel(name=payload.name)
    db.add(new_deanery)
    await db.commit()
    await db.refresh(new_deanery)

    return new_deanery


@router.get("/", response_model=List[DeaneryResponse])
async def get_all_deaneries(
        db: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_read_access)
):
    """Fetches a list of all Deaneries in the Diocese."""
    query = select(DeaneryModel).order_by(DeaneryModel.name)
    result = await db.execute(query)
    return result.scalars().all()


# ==============================================================================
# 2. PROVISIONING: REGISTER A NEW PARISH (SYSADMIN)
# ==============================================================================
@router.post("/{deanery_id}/parishes", response_model=ParishResponse, status_code=status.HTTP_201_CREATED)
async def register_parish(
        deanery_id: int,
        payload: ParishCreate,
        db: AsyncSession = Depends(get_db),
        _admin: User = Depends(require_sysadmin_access)
):
    """
    Registers a new Parish and assigns it to a Deanery.
    Establishes the internal 'schema_name' used for tenant data isolation.
    """
    deanery_query = select(DeaneryModel).where(DeaneryModel.id == deanery_id)
    if not (await db.execute(deanery_query)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deanery not found.")

    schema_query = select(ParishModel).where(ParishModel.schema_name == payload.schema_name)
    if (await db.execute(schema_query)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A parish with this schema_name already exists.")

    new_parish = ParishModel(
        name=payload.name,
        deanery_id=deanery_id,
        schema_name=payload.schema_name
    )
    db.add(new_parish)
    await db.commit()
    await db.refresh(new_parish)

    return new_parish


# ==============================================================================
# 3. ANALYTICS: DEANERY DASHBOARD & OVERVIEW (DEANS & BISHOP)
# ==============================================================================
@router.get("/{deanery_id}/overview")
async def get_deanery_overview(
        deanery_id: int,
        db: AsyncSession = Depends(get_db),
        admin_user: User = Depends(verify_deanery_role)
):
    """Returns the aggregated Sacramental and Financial totals for a specific Deanery."""

    # Security Check: A Dean can only view his OWN deanery. The Bishop/SysAdmin bypasses this.
    if admin_user.role == "Dean" and admin_user.deanery_id != deanery_id:
        raise HTTPException(status_code=403, detail="You do not have jurisdiction over this Deanery.")

    query = (
        select(
            func.sum(DiocesanAnalyticsModel.total_baptisms_ytd).label("total_baptisms"),
            func.sum(DiocesanAnalyticsModel.total_communions_ytd).label("total_communions"),
            func.sum(DiocesanAnalyticsModel.total_confirmations_ytd).label("total_confirmations"),
            func.sum(DiocesanAnalyticsModel.total_marriages_ytd).label("total_marriages"),
            func.sum(DiocesanAnalyticsModel.total_deaths_ytd).label("total_deaths"),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_target_ytd).label("total_target"),
            func.sum(DiocesanAnalyticsModel.diocesan_contributions_actual_ytd).label("total_actual")
        )
        .join(ParishModel, DiocesanAnalyticsModel.parish_id == ParishModel.id)
        .where(ParishModel.deanery_id == deanery_id)
    )
    result = (await db.execute(query)).one()

    target = result.total_target or 0
    actual = result.total_actual or 0

    return {
        "deanery_sacramental_totals": {
            "baptisms": result.total_baptisms or 0,
            "first_communions": result.total_communions or 0,
            "confirmations": result.total_confirmations or 0,
            "marriages": result.total_marriages or 0,
            "deaths": result.total_deaths or 0,
        },
        "deanery_financial_health": {
            "total_cdom_target_zmw": float(target),
            "total_cdom_actual_zmw": float(actual),
            "variance_zmw": float(actual - target)
        }
    }


# ==============================================================================
# 4. ANALYTICS: INDIVIDUAL PARISH BREAKDOWN (DEANS & BISHOP)
# ==============================================================================
@router.get("/{deanery_id}/parish-analytics")
async def get_deanery_parishes_analytics(
        deanery_id: int,
        db: AsyncSession = Depends(get_db),
        admin_user: User = Depends(verify_deanery_role)
):
    """Returns the individual analytics rows for parishes strictly within this Deanery."""

    if admin_user.role == "Dean" and admin_user.deanery_id != deanery_id:
        raise HTTPException(status_code=403, detail="Unauthorized. You do not have jurisdiction over this Deanery.")

    query = (
        select(DiocesanAnalyticsModel)
        .join(ParishModel, DiocesanAnalyticsModel.parish_id == ParishModel.id)
        .where(ParishModel.deanery_id == deanery_id)
    )
    result = await db.execute(query)

    return result.scalars().all()