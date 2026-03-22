from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # App Config
    PROJECT_NAME: str = Field(default="CDOM Management System")

    # Database Config
    DATABASE_URL: str

    # Security Config
    SECRET_KEY: str
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=120)

    # Email Config (Resend)
    RESEND_API_KEY: str = Field(default="")

    # Tells Pydantic to read from the .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()