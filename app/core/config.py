from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    CDOM Registry Configuration Settings.
    Loads variables from the .env file using Pydantic Settings.
    """

    # App Config
    PROJECT_NAME: str = Field(default="CDOM Management System")

    # Database Config
    DATABASE_URL: str
    TEST_DATABASE_URL: str = Field(default="")

    # Security Config
    SECRET_KEY: str
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=120)

    # Email Config (Resend)
    RESEND_API_KEY: str = Field(default="")

    # Tells Pydantic to read from the .env file.
    # We use 'extra="ignore"' to prevent errors if other variables exist in .env
    # Note: If running from outside the backend folder in PyCharm, you might need env_file="backend/.env"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Instantiate the settings object
settings = Settings()

# ==============================================================================
# DEBUG: SECURITY VERIFICATION
# ==============================================================================
# This will print to your PyCharm console/terminal on server startup.
# It verifies that the .env file is actually being read and the key is loaded.
# (If Uvicorn crashes before printing this, it means Pydantic cannot find your .env file at all!)
print(f"DEBUG: Secret Key Loaded: {settings.SECRET_KEY[:5]}...")