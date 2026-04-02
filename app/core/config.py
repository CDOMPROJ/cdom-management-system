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
    RESEND_API_KEY: Optional[str] = "re_f3FomECj_83AbckvFY6RqEY2ZRL2C7yu7"

    # Security defaults
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Strict environment binding
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()