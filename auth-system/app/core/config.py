import os
from typing import Optional
from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Read from .env if present. We load it relative to the root/cwd directory
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # General App Settings
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "FastAPI Auth System"

    # Security Settings
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration
    DATABASE_URL: str

    # Admin / First Superuser Seeding
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: EmailStr = "admin@example.com"
    ADMIN_PASSWORD: str = "SuperSecurePassword123!"

    # Mocked or Real mail configurations
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[EmailStr] = None
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 2
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 24

    @property
    def IS_TESTING(self) -> bool:
        return self.ENVIRONMENT == "testing"

# Instantiate settings to expose to the rest of the application
settings = Settings()
