# ==============================================================================
# CDOM PASTORAL MANAGEMENT SYSTEM – ALL MODELS (SINGLE FILE)
# Centralized location for ALL SQLAlchemy models. Used by Alembic and FastAPI.
# Phase 3.1: Fine-grained RBAC + ABAC + object ownership + session management
# Exact 8 offices with spaces as per repo. No hallucinated permissions.
# ==============================================================================

from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Numeric, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime, timezone

Base = declarative_base()


# ==============================================================================
# 0. ENUMS (EXACT 8 OFFICES WITH SPACES – LOCKED FROM REPO)
# ==============================================================================
class Office(str, enum.Enum):
    BISHOP = "Bishop"
    SYS_ADMIN = "Sys Admin"
    DEAN = "Dean"
    DEANERY_YOUTH_CHAPLAIN = "Deanery Youth Chaplain"
    PARISH_PRIEST = "Parish Priest"
    ASSISTANT_PRIEST = "Assistant Priest"
    PARISH_YOUTH_CHAPLAIN = "Parish Youth Chaplain"
    PARISH_SECRETARY = "Parish Secretary"


class ReligionCategory(str, enum.Enum):
    CATHOLIC = "Catholic"
    OTHER_CHRISTIAN = "Other Christian"
    NON_CHRISTIAN = "Non-Christian"


class TransactionType(str, enum.Enum):
    INCOME = "Income"
    EXPENSE = "Expense"


# ==============================================================================
# 1. NEW RBAC/ABAC MODELS
# ==============================================================================
class Permission(Base):
    __tablename__ = "permissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    scope_level = Column(String, nullable=False, index=True)  # diocese | deanery | parish | global
    resource_type = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role = Column(Enum(Office), primary_key=True, nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True, nullable=False)


# ==============================================================================
# 2. NEW SESSION & DEVICE MANAGEMENT MODELS
# ==============================================================================
class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_fingerprint = Column(String, nullable=False, index=True)
    ip_address = Column(String, nullable=False)
    user_agent = Column(Text, nullable=False)
    last_active = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_trusted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="sessions")


class ElevatedToken(Base):
    __tablename__ = "elevated_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)

    user = relationship("User")


# ==============================================================================
# 3. EXISTING MODELS + OWNERSHIP COLUMNS (full expansion)
# ==============================================================================
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    office = Column(Enum(Office), nullable=False)
    parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True)
    deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True)
    token_version = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    password_history = Column(JSONB, default=list, nullable=False)
    last_password_change = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    lockout_until = Column(DateTime(timezone=True), nullable=True)
    webauthn_credentials = Column(JSONB, default=list, nullable=False)
    permissions_cache = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), nullable=False)

    revoked_tokens = relationship("RevokedTokenModel", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class RevokedTokenModel(Base):
    __tablename__ = "revoked_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    reason = Column(String, nullable=True)
    user = relationship("User", back_populates="revoked_tokens")


class DeaneryModel(Base):
    __tablename__ = "deaneries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class ParishModel(Base):
    __tablename__ = "parishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    deanery_id = Column(Integer, ForeignKey("deaneries.id", ondelete="RESTRICT"), index=True)
    schema_name = Column(String, unique=True)


class UserInvitationModel(Base):
    __tablename__ = "user_invitations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)
    office = Column(Enum(Office), nullable=False)
    parish_id = Column(Integer, nullable=True)
    deanery_id = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(String, nullable=False, index=True)
    target_table = Column(String, nullable=False, index=True)
    target_record_id = Column(String, nullable=False, index=True)
    changed_by = Column(String, nullable=False)
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


class GlobalRegistryIndex(Base):
    __tablename__ = "global_registry_index"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_type = Column(String, nullable=False, index=True)
    canonical_number = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    date_of_event = Column(Date, nullable=True, index=True)
    indexed_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


class ClergyRegistryModel(Base):
    __tablename__ = "clergy_registry"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String, nullable=False, index=True)
    congregation = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    current_location = Column(String, nullable=True)
    ministry_category = Column(String, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String, nullable=False)
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    communications = relationship("ActionPlanCommunicationModel", back_populates="plan", cascade="all, delete-orphan")


class ActionPlanCommunicationModel(Base):
    __tablename__ = "action_plan_communications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("youth_action_plans.id", ondelete="CASCADE"), index=True)
    sender_email = Column(String, nullable=False)
    sender_role = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False)
    recipient_role = Column(String, nullable=False)
    action_taken = Column(String, nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    plan = relationship("YouthActionPlanModel", back_populates="communications")


class DiocesanAnalyticsModel(Base):
    __tablename__ = "diocesan_analytics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    owner_parish_id = Column(Integer, ForeignKey("parishes.id"), nullable=True, index=True)
    owner_deanery_id = Column(Integer, ForeignKey("deaneries.id"), nullable=True, index=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)


# ==============================================================================
# END OF ALL MODELS
# ==============================================================================