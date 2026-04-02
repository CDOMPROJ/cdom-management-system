from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "CDOM Management System"
    VERSION: str = "1.0.0"

    # Core Database & Security (MUST exist in .env)
    DATABASE_URL: str
    SECRET_KEY: str

    # External APIs
    # Using Optional/default so the server doesn't crash if you haven't put a real key in .env yet
    RESEND_API_KEY: Optional[str] = "So_Dumm_If_You_Put_Secret_Key_Here"

    # Security defaults
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Strict environment binding
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()