# ==========================================
# CDOM Pastoral Management System – Schemas Export
# Central __init__.py for clean imports
# Single source of truth: app/schemas/schemas.py
# ==========================================

"""Central export file for all Pydantic schemas.
This allows clean imports like:
    from app.schemas import BaptismCreate, Token, ErrorResponse, MarriageResponse
"""

# ==========================================
# 1. COMMON / SHARED SCHEMAS
# ==========================================
from .schemas import (
    PaginatedResponse,
    ReligionCategory,
    ErrorResponse,
)

# ==========================================
# 2. GEOGRAPHY SCHEMAS
# ==========================================
from .schemas import (
    DeaneryBase,
    DeaneryCreate,
    DeaneryResponse,
    ParishBase,
    ParishCreate,
    ParishResponse,
)

# ==========================================
# 3. AUTHENTICATION & SECURITY SCHEMAS (SecurityPatch)
# ==========================================
from .schemas import (
    Token,
    TokenRefresh,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    MFAVerifyRequest,
    MFASetupResponse,
    UserInviteRequest,
    UserSetupRequest,
    TokenData,
    UserCreate,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    DirectUserCreateRequest,
)

# ==========================================
# 4. SACRAMENTAL REGISTER SCHEMAS
# ==========================================
from .schemas import (
    # Baptism
    BaptismBase,
    BaptismCreate,
    BaptismResponse,
    # Marriage
    MarriageBase,
    MarriageCreate,
    MarriageResponse,
    # First Communion
    FirstCommunionBase,
    FirstCommunionCreate,
    FirstCommunionResponse,
    # Confirmation
    ConfirmationBase,
    ConfirmationCreate,
    ConfirmationResponse,
    # Death Register
    DeathRegisterBase,
    DeathRegisterCreate,
    DeathRegisterResponse,
)

# ==========================================
# 5. FINANCE & CLERGY SCHEMAS
# ==========================================
from .schemas import (
    FinanceBase,
    FinanceCreate,
    FinanceResponse,
    DiocesanContributionUpdate,
    DiocesanContributionResponse,
    ClergyRegistryBase,
    ClergyRegistryCreate,
    ClergyRegistryResponse,
)

# ==========================================
# 6. YOUTH MINISTRY SCHEMAS
# ==========================================
from .schemas import (
    YouthProfileBase,
    YouthProfileCreate,
    YouthProfileResponse,
    CommunicationBase,
    CommunicationResponse,
    YouthActionPlanBase,
    YouthActionPlanCreate,
    YouthActionPlanResponse,
)

# ==========================================
# 7. GLOBAL SEARCH & GOVERNANCE SCHEMAS
# ==========================================
from .schemas import (
    GlobalSearchResult,
    SearchResponse,
    PendingActionBase,
    PendingActionCreate,
    PendingActionResponse,
)