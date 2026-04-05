# app/schemas/__init__.py
from .schemas import (
    PaginatedResponse,
    ReligionCategory,
    DeaneryBase,
    DeaneryCreate,
    DeaneryResponse,
    ParishBase,
    ParishCreate,
    ParishResponse,
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    MFAVerifyRequest,
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

from .baptism import (
    BaptismBase,
    BaptismCreate,
    BaptismResponse,
)

from .marriage import (
    MarriageBase,
    MarriageCreate,
    MarriageResponse,
)

from .first_communion import (
    FirstCommunionBase,
    FirstCommunionCreate,
    FirstCommunionResponse,
)

from .confirmation import (
    ConfirmationBase,
    ConfirmationCreate,
    ConfirmationResponse,
)

from .death_register import (
    DeathRegisterBase,
    DeathRegisterCreate,
    DeathRegisterResponse,
)

from .finances import (
    FinanceBase,
    FinanceCreate,
    FinanceResponse,
    DiocesanContributionUpdate,
)