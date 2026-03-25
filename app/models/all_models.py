from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Numeric, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()


# ==============================================================================
# 0. ENUMS (STRICT CANONICAL & FINANCIAL CATEGORIZATION)
# ==============================================================================
class ReligionCategory(str, enum.Enum):
    CATHOLIC = "Catholic"
    OTHER_CHRISTIAN = "Other Christian"
    NON_CHRISTIAN = "Non-Christian"


class TransactionType(str, enum.Enum):
    INCOME = "Income"
    EXPENSE = "Expense"


class IncomeCategory(str, enum.Enum):
    ICISUMINO_CANDI = "Icisumino Candi"
    UBULOBOLOLO = "Ubulobololo (Harvest Total)"
    SUNDAY_COLLECTIONS = "Sunday Collections"
    SPECIAL_COLLECTIONS = "Special Collections"
    FUNDRAISING = "Fundraising"
    DONATIONS = "Donations"
    ASSET_YIELDS = "Asset Yields"


class ExpenseCategory(str, enum.Enum):
    DIOCESAN_ASSESSMENT_REMITTANCE = "Diocesan Assessment Remittance"
    PASTORAL_LITURGICAL = "Pastoral & Liturgical"
    CLERGY_WELFARE = "Clergy Welfare"
    ADMINISTRATION = "Administration"
    UTILITIES = "Utilities"
    WAGES_AND_SALARIES = "Wages and Salaries"
    MAINTENANCE = "Maintenance"
    APOSTOLATE_FUNDING = "Apostolate Funding"
    CHARITY = "Charity"


class DiocesanFundCategory1(str, enum.Enum):
    UMUTULO_WAKU_DIOCESE = "Umutulo waku Diocese"
    SOLIDARITY_FUND = "Solidarity Fund"
    SEMINARIAN_FUND = "Seminarian Fund"


class DiocesanFundCategory2(str, enum.Enum):
    EPIPHANY = "Epiphany"
    HOLY_LAND = "Holy Land"
    LAZARO_MULANDA = "Lazaro Mulanda"
    VOCATION_SUNDAY = "Vocation Sunday"
    MENS_PASTORAL_FUND = "Men's Pastoral Fund"
    BIBLE = "Bible"
    MISSION_SUNDAY = "Mission Sunday"
    PAPA = "Papa (Peter and Paul)"
    COMMUNICATION_SUNDAY = "Communication Sunday"


# ==============================================================================
# 1. GEOGRAPHY & IDENTITY (PUBLIC SCHEMA)
# ==============================================================================
class DeaneryModel(Base):
    __tablename__ = "deaneries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class ParishModel(Base):
    __tablename__ = "parishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    # INDEX ADDED: Speeds up deanery-level aggregations
    deanery_id = Column(Integer, ForeignKey("deaneries.id", ondelete="RESTRICT"), index=True)
    schema_name = Column(String, unique=True)


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    office = Column(String, nullable=False)


    # INDEXES ADDED: Speeds up RBAC and geographical authorization
    parish_id = Column(Integer, ForeignKey("parishes.id", ondelete="SET NULL"), nullable=True, index=True)
    deanery_id = Column(Integer, ForeignKey("deaneries.id", ondelete="SET NULL"), nullable=True, index=True)
    reset_token = Column(String, unique=True, index=True, nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserInvitationModel(Base):
    __tablename__ = "user_invitations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)
    office = Column(String, nullable=False)
    parish_id = Column(Integer, nullable=True)
    deanery_id = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


# ==============================================================================
# 2. GOVERNANCE & AUDIT (IMMUTABLE LEDGER)
# ==============================================================================
class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(String, nullable=False, index=True)
    target_table = Column(String, nullable=False, index=True)
    target_record_id = Column(String, nullable=False, index=True)
    changed_by = Column(String, nullable=False)
    # INDEX ADDED
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    previous_payload = Column(JSONB, nullable=True)
    new_payload = Column(JSONB, nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class PendingActionModel(Base):
    __tablename__ = "pending_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    target_table = Column(String, nullable=False)
    target_record_id = Column(String, nullable=False)
    proposed_payload = Column(JSONB, nullable=False)
    status = Column(String, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# 3. GLOBAL INTELLIGENCE INDEX
# ==============================================================================
class GlobalRegistryIndex(Base):
    __tablename__ = "global_registry_index"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_type = Column(String, nullable=False, index=True)
    canonical_number = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    # INDEX ADDED: Crucial for lightning-fast Sacramental ETL aggregation
    parish_id = Column(Integer, ForeignKey("parishes.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# 4. SACRAMENTAL MODELS
# ==============================================================================
class BaptismModel(Base):
    __tablename__ = "baptisms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    village = Column(String, nullable=False)
    father_first_name = Column(String, nullable=False)
    father_last_name = Column(String, nullable=False)
    mother_first_name = Column(String, nullable=False)
    mother_last_name = Column(String, nullable=False)
    godparents = Column(String, nullable=False)
    date_of_baptism = Column(Date, nullable=False)
    minister_of_baptism = Column(String, nullable=False)
    registry_year = Column(Integer, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    formatted_number = Column(String, nullable=False, unique=True, index=True)
    is_deceased = Column(Boolean, default=False)
    death_record_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FirstCommunionModel(Base):
    __tablename__ = "first_communions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    baptism_number = Column(String, nullable=True)
    communion_date = Column(Date, nullable=False)
    minister = Column(String, nullable=False)
    registry_year = Column(Integer, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    formatted_number = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConfirmationModel(Base):
    __tablename__ = "confirmations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    confirmation_name = Column(String, nullable=True)
    baptism_number = Column(String, nullable=True)
    sponsor_name = Column(String, nullable=False)
    confirmation_date = Column(Date, nullable=False)
    minister = Column(String, nullable=False)
    registry_year = Column(Integer, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    formatted_number = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarriageModel(Base):
    __tablename__ = "marriages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    groom_first_name = Column(String, nullable=False)
    groom_last_name = Column(String, nullable=False)
    groom_baptism_number = Column(String, nullable=True)
    groom_religion = Column(Enum(ReligionCategory), nullable=False)
    bride_first_name = Column(String, nullable=False)
    bride_last_name = Column(String, nullable=False)
    bride_baptism_number = Column(String, nullable=True)
    bride_religion = Column(Enum(ReligionCategory), nullable=False)
    marriage_date = Column(Date, nullable=False)
    minister = Column(String, nullable=False)
    witness_1 = Column(String, nullable=False)
    witness_2 = Column(String, nullable=False)
    registry_year = Column(Integer, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    formatted_number = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DeathRegisterModel(Base):
    __tablename__ = "death_register"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=False)
    date_of_death = Column(Date, nullable=False)
    cause_of_death = Column(String, nullable=True)
    cemetery = Column(String, nullable=False)
    sacraments_received = Column(Boolean, default=False)
    minister = Column(String, nullable=False)
    baptism_number = Column(String, nullable=True)
    registry_year = Column(Integer, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    formatted_number = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==============================================================================
# 5. FINANCIAL MODELS (PARISH LEDGER & UMUTULO)
# ==============================================================================
class FinanceModel(Base):
    __tablename__ = "parish_finances"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer)
    transaction_date = Column(Date, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    recorded_by = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DiocesanContributionModel(Base):
    __tablename__ = "diocesan_contributions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporting_year = Column(Integer, index=True)
    fund_name = Column(String, nullable=False)
    fund_type = Column(String, nullable=False)
    target_amount = Column(Numeric(12, 2), nullable=True)
    actual_amount_paid = Column(Numeric(12, 2), default=0.00)
    variance_amount = Column(Numeric(12, 2), nullable=True)
    last_payment_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ==============================================================================
# 6. YOUTH MINISTRY & COMMUNICATIONS
# ==============================================================================
class YouthProfileModel(Base):
    __tablename__ = "youth_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    parent_guardian_name = Column(String, nullable=False)
    contact_number = Column(String, nullable=True)
    village_center = Column(String, nullable=False)
    is_baptised = Column(Boolean, default=False)
    is_communicant = Column(Boolean, default=False)
    is_confirmed = Column(Boolean, default=False)
    canonical_baptism_number = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class YouthActionPlanModel(Base):
    __tablename__ = "youth_action_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    academic_year = Column(Integer)
    title = Column(String)
    objectives = Column(Text)
    target_demographic = Column(String)
    proposed_budget = Column(Numeric(10, 2), default=0.00)
    status = Column(String, default="DRAFT")
    pp_feedback = Column(Text, nullable=True)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    communications = relationship("ActionPlanCommunicationModel", back_populates="plan", cascade="all, delete-orphan")


class ActionPlanCommunicationModel(Base):
    __tablename__ = "action_plan_communications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # INDEX ADDED: Essential for quick retrieval of email threads
    plan_id = Column(UUID(as_uuid=True), ForeignKey("youth_action_plans.id", ondelete="CASCADE"), index=True)
    sender_email = Column(String, nullable=False)
    sender_role = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False)
    recipient_role = Column(String, nullable=False)
    action_taken = Column(String, nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    plan = relationship("YouthActionPlanModel", back_populates="communications")


# ==============================================================================
# 7. ANALYTICS (GOLD LAYER)
# ==============================================================================
class DiocesanAnalyticsModel(Base):
    __tablename__ = "diocesan_analytics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # INDEX ADDED: Accelerates the Bishop's Dashboard queries
    parish_id = Column(Integer, ForeignKey("parishes.id", ondelete="CASCADE"), index=True)
    parish_name = Column(String, nullable=False)
    reporting_year = Column(Integer, nullable=False, index=True)
    total_baptisms_ytd = Column(Integer, default=0)
    total_communions_ytd = Column(Integer, default=0)
    total_confirmations_ytd = Column(Integer, default=0)
    total_marriages_ytd = Column(Integer, default=0)
    total_deaths_ytd = Column(Integer, default=0)
    diocesan_contributions_target_ytd = Column(Numeric(12, 2), default=0.00)
    diocesan_contributions_actual_ytd = Column(Numeric(12, 2), default=0.00)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())