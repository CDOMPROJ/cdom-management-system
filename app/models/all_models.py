from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Numeric, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()


# ==============================================================================
# ENUMS (CANON LAW & DATA CLASSIFICATION)
# ==============================================================================
class ReligionCategory(str, enum.Enum):
    """Categorizes religion for Canonical Marriage statistics (Mixed Religion vs Disparity of Cult)."""
    CATHOLIC = "Catholic"
    OTHER_CHRISTIAN = "Other Christian"
    NON_CHRISTIAN = "Non-Christian"


# ==============================================================================
# SECTION 1: PUBLIC SCHEMA (GLOBAL IDENTITY, ACCESS & AGGREGATE STATS)
# ==============================================================================
class DeaneryModel(Base):
    __tablename__ = "deaneries"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class ParishModel(Base):
    __tablename__ = "parishes"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    deanery_id = Column(Integer, ForeignKey("public.deaneries.id"))
    schema_name = Column(String, unique=True, index=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, index=True)
    office = Column(String, nullable=True)
    parish_id = Column(Integer, ForeignKey("public.parishes.id"), nullable=True)
    deanery_id = Column(Integer, ForeignKey("public.deaneries.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    session_id = Column(String, nullable=True)


class GlobalRegistryIndex(Base):
    __tablename__ = "global_registry_index"
    __table_args__ = {"schema": "public"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    canonical_number = Column(String, index=True)
    baptism_number = Column(String, index=True, nullable=True)
    record_type = Column(String, index=True)
    parish_id = Column(Integer, ForeignKey("public.parishes.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnnualParishCensusModel(Base):
    """GOLD LAYER: Aggregate non-canonical data for the Bishop's Annual Statistics PDF."""
    __tablename__ = "annual_parish_census"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True)
    parish_id = Column(Integer, ForeignKey("public.parishes.id"))
    reporting_year = Column(Integer)

    # Staff & Converts (PDF Items 5, 6, 7)
    catechumens_count = Column(Integer, default=0)
    converts_without_conditional_baptism = Column(Integer, default=0)
    paid_catechists = Column(Integer, default=0)
    voluntary_catechists = Column(Integer, default=0)

    # Demographics (PDF Items 8, 9)
    total_catholic_population = Column(Integer, default=0)
    other_christians = Column(Integer, default=0)
    non_christians = Column(Integer, default=0)


class DemographicTrendModel(Base):
    """GOLD LAYER: Pre-calculated trends for Diocesan Planning (ML Target)."""
    __tablename__ = "demographic_trends"
    __table_args__ = {"schema": "public"}
    id = Column(Integer, primary_key=True)
    parish_id = Column(Integer, ForeignKey("public.parishes.id"))
    year = Column(Integer)

    baptism_count = Column(Integer)
    projected_youth_growth_rate = Column(Numeric(5, 2))  # Predicted by ML
    predicted_sacrament_demand = Column(JSONB)  # e.g., {"Confirmations_2027": 150}
    last_updated = Column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# SECTION 2: PARISH SCHEMA (GOVERNANCE & AUDIT TRAIL)
# ==============================================================================
class AuditLogModel(Base):
    """
    A tamper-proof ledger tracking all approved modifications to canonical records.
    Moved to the 'public' schema so the Bishop can audit the entire Diocese from one table.
    """
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(String, nullable=False)
    target_table = Column(String, nullable=False)
    target_record_id = Column(String, nullable=False, index=True)
    changed_by_email = Column(String, nullable=False, index=True)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class PendingActionModel(Base):
    __tablename__ = "pending_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by = Column(String, index=True)
    action_type = Column(String)
    target_table = Column(String)
    target_record_id = Column(String)
    proposed_payload = Column(JSONB)
    status = Column(String, default="PENDING")
    reviewed_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# SECTION 3: PARISH SCHEMA (SACRAMENTAL REGISTERS)
# ==============================================================================
class BaptismModel(Base):
    __tablename__ = "baptisms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    registry_year = Column(Integer)
    formatted_number = Column(String, unique=True, index=True)
    first_name = Column(String)
    middle_name = Column(String, nullable=True)
    last_name = Column(String)
    dob = Column(Date)  # REQUIRED for statistical age bracketing
    date_of_baptism = Column(Date)
    minister_of_baptism = Column(String)
    father_first_name = Column(String)
    father_last_name = Column(String)
    mother_first_name = Column(String)
    mother_last_name = Column(String)
    godparents = Column(String)
    village = Column(String)
    center = Column(String)
    first_communion_id = Column(UUID(as_uuid=True), nullable=True)
    confirmation_id = Column(UUID(as_uuid=True), nullable=True)
    marriage_id = Column(UUID(as_uuid=True), nullable=True)
    is_deceased = Column(Boolean, default=False)
    death_record_id = Column(UUID(as_uuid=True), nullable=True)


class FirstCommunionModel(Base):
    __tablename__ = "first_communions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    registry_year = Column(Integer)
    formatted_number = Column(String, unique=True, index=True)
    first_name = Column(String)
    middle_name = Column(String, nullable=True)
    last_name = Column(String)
    father_first_name = Column(String)
    father_last_name = Column(String)
    mother_first_name = Column(String)
    mother_last_name = Column(String)
    baptism_number = Column(String, index=True)
    baptised_at = Column(String)
    communion_date = Column(Date)
    minister = Column(String)
    place_of_communion = Column(String)


class ConfirmationModel(Base):
    __tablename__ = "confirmations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    registry_year = Column(Integer)
    formatted_number = Column(String, unique=True, index=True)
    first_name = Column(String)
    middle_name = Column(String, nullable=True)
    last_name = Column(String)
    dob = Column(Date)  # REQUIRED for statistical age bracketing (Adult vs Child)
    father_first_name = Column(String)
    father_last_name = Column(String)
    mother_first_name = Column(String)
    mother_last_name = Column(String)
    baptism_number = Column(String, index=True)
    baptised_at = Column(String)
    confirmation_date = Column(Date)
    minister = Column(String)
    place_of_confirmation = Column(String)
    god_parent = Column(String)
    god_parent_is_baptised = Column(Boolean)
    god_parent_is_confirmed = Column(Boolean)


class MarriageModel(Base):
    __tablename__ = "marriages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    sequential_number = Column(Integer)
    registry_year = Column(Integer)
    formatted_number = Column(String, unique=True, index=True)

    # Groom Details
    groom_first_name = Column(String)
    groom_middle_name = Column(String, nullable=True)
    groom_last_name = Column(String)
    groom_father_first_name = Column(String)
    groom_father_last_name = Column(String)
    groom_mother_first_name = Column(String)
    groom_mother_last_name = Column(String)
    groom_dob = Column(Date)
    groom_baptised_at = Column(String)
    groom_baptism_number = Column(String, index=True)
    groom_religion_category = Column(Enum(ReligionCategory), default=ReligionCategory.CATHOLIC, nullable=False)
    groom_religion_specific = Column(String, nullable=True)  # e.g., "SDA", "Muslim"

    # Bride Details
    bride_first_name = Column(String)
    bride_middle_name = Column(String, nullable=True)
    bride_last_name = Column(String)
    bride_father_first_name = Column(String)
    bride_father_last_name = Column(String)
    bride_mother_first_name = Column(String)
    bride_mother_last_name = Column(String)
    bride_dob = Column(Date)
    bride_baptised_at = Column(String)
    bride_baptism_number = Column(String, index=True)
    bride_religion_category = Column(Enum(ReligionCategory), default=ReligionCategory.CATHOLIC, nullable=False)
    bride_religion_specific = Column(String, nullable=True)  # e.g., "UCZ", "Traditional"

    # Event Details
    marriage_date = Column(Date)
    place_of_marriage = Column(String)
    minister = Column(String)
    witness_1 = Column(String)
    witness_2 = Column(String)
    banns_published_on = Column(Date, nullable=True)
    dispensation_from_impediment = Column(String, nullable=True)


class DeathRegisterModel(Base):
    __tablename__ = "death_register"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    registry_year = Column(Integer)
    formatted_number = Column(String, unique=True, index=True)
    first_name = Column(String)
    middle_name = Column(String, nullable=True)
    last_name = Column(String)
    baptism_number = Column(String, nullable=True, index=True)
    date_of_death = Column(Date)
    date_of_burial = Column(Date)
    place_of_burial = Column(String)
    minister_of_rites = Column(String)
    received_last_rites = Column(Boolean, default=False)


# ==============================================================================
# SECTION 4: PARISH SCHEMA (FINANCIAL LEDGERS)
# ==============================================================================
class FinanceModel(Base):
    __tablename__ = "parish_finances"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    transaction_date = Column(Date)
    transaction_type = Column(String)
    category = Column(String)
    amount = Column(Numeric(10, 2))
    notes = Column(Text, nullable=True)


class DiocesanContributionModel(Base):
    __tablename__ = "diocesan_contributions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    reporting_year = Column(Integer)
    fund_name = Column(String)
    target_amount = Column(Numeric(12, 2), nullable=True)
    actual_amount = Column(Numeric(12, 2), default=0.00)
    variance_amount = Column(Numeric(12, 2), nullable=True)
    notes = Column(Text, nullable=True)


# ==============================================================================
# SECTION 5: PARISH SCHEMA (YOUTH MINISTRY & CATECHESIS)
# ==============================================================================
class YouthProfileModel(Base):
    """Tracks children and youth demographics, catechumens, and sacramental progress."""
    __tablename__ = "youth_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    dob = Column(Date)
    parent_guardian_name = Column(String)
    contact_number = Column(String, nullable=True)
    village_center = Column(String)

    # Sacramental Tracking
    is_baptised = Column(Boolean, default=False)
    is_communicant = Column(Boolean, default=False)
    is_confirmed = Column(Boolean, default=False)
    canonical_baptism_number = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class YouthActionPlanModel(Base):
    """Workflow model for Youth Chaplains creating plans for Parish Priest approval."""
    __tablename__ = "youth_action_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    academic_year = Column(Integer)
    title = Column(String)
    objectives = Column(Text)
    target_demographic = Column(String)
    proposed_budget = Column(Numeric(10, 2), default=0.00)

    # State Machine: DRAFT -> PENDING_PP -> APPROVED_PP -> SUBMITTED_DEANERY
    status = Column(String, default="DRAFT")
    pp_feedback = Column(Text, nullable=True)

    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())