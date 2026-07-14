import os
import re
from typing import Optional
from pydantic import EmailStr, field_validator
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
    PROJECT_NAME: str = "ConVex API"

    # Security Settings
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Rotated on every /auth/refresh call (see app.services.auth.refresh_access_token), so this
    # is a sliding window, not a hard cap - a user who opens the app at least this often stays
    # signed in indefinitely without re-entering their password.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60

    # Database Configuration
    DATABASE_URL: str

    # Admin / First Superuser Seeding
    # No default on ADMIN_PASSWORD (unlike ADMIN_USERNAME/EMAIL) - a hardcoded password default
    # would ship a known, publicly-visible admin credential to any deployment that forgot to set
    # it, same reasoning as JWT_SECRET_KEY having no default. The app fails to start without it.
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: EmailStr = "admin@example.com"
    ADMIN_PASSWORD: str

    # Mocked or Real mail configurations
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[EmailStr] = None
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 2
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 24

    @field_validator("EMAIL_FROM", mode="before")
    @classmethod
    def _blank_email_from_is_unset(cls, v):
        # An empty EMAIL_FROM= line in .env loads as "" (a string), not Python None, and ""
        # fails EmailStr's format check - treat blank the same as absent rather than a startup
        # crash over an unset optional setting.
        return v or None

    # Study Session / Anti-cheat Settings
    # Client is expected to ping /heartbeat roughly every 20-30s while foregrounded.
    STUDY_HEARTBEAT_GRACE_SECONDS: int = 45  # gaps longer than this aren't credited (background/kill)
    STUDY_SESSION_STALE_TIMEOUT_SECONDS: int = 1200  # 20 min silence auto-flags the session
    STUDY_CHECK_MIN_INTERVAL_SECONDS: int = 300  # 5 min
    STUDY_CHECK_MAX_INTERVAL_SECONDS: int = 600  # 10 min
    STUDY_ATTENTION_CHECK_WINDOW_SECONDS: int = 15  # tap-to-confirm response window
    STUDY_RECALL_CHECK_WINDOW_SECONDS: int = 45  # short free-text response window
    STUDY_CHECK_MAX_FAILURES: int = 2  # missed/failed checks before a session is auto-flagged

    # Reward payout control (verified minutes feed the rewards engine; see
    # app.services.reward for the minutes -> Knowledge Points -> GHS conversion and redemption tiers)
    STUDY_DAILY_VERIFIED_MINUTES_CAP: int = 180  # 3h/day
    STUDY_WEEKLY_VERIFIED_MINUTES_CAP: int = 900  # 15h/week

    # Paystack (Transfers pay redemptions out, Transactions charge subscriptions in).
    # Left unset in dev: app.services.reward falls back to a mocked payout when missing;
    # app.services.subscription requires it (there's no sensible mock for "did they pay").
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PAYSTACK_SECRET_KEY: Optional[str] = None

    # Where Paystack redirects the browser after a subscription payment attempt.
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # CORS: comma-separated list of origins allowed to call this API (the deployed frontend
    # URL(s)). Defaults to the local Vite dev server so local dev keeps working unconfigured.
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # AI quiz generation for guided study sessions (app.services.ai_client). Using Gemini's free
    # tier for now, isolated behind one function so swapping to Claude later doesn't touch
    # anything else. Left unset in dev: start_guided_session fails closed with 503 rather than
    # faking a quiz - unlike a mocked payout, a fabricated quiz would actively mislead a student.
    GEMINI_API_KEY: Optional[str] = None
    # "gemini-2.0-flash" returns 429 RESOURCE_EXHAUSTED with a hard 0 free-tier quota for newer
    # API keys/projects - Google appears to have stopped granting free quota on that pinned model
    # name. The rolling "-latest" alias (currently pointing at the 2.5 flash generation) does have
    # free quota and was verified end-to-end (including structured JSON output) against a real key.
    GEMINI_MODEL: str = "gemini-flash-latest"

    @property
    def PAYSTACK_CONFIGURED(self) -> bool:
        return bool(self.PAYSTACK_SECRET_KEY)

    @property
    def AI_CONFIGURED(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @property
    def SMTP_CONFIGURED(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def IS_TESTING(self) -> bool:
        return self.ENVIRONMENT == "testing"

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """DATABASE_URL, normalized for the async drivers this app actually uses.

        Most hosted Postgres providers (Neon, Render, Supabase, Heroku-style) hand out bare
        postgres:// or postgresql:// URLs with a sslmode=require query param - that's meant for
        psycopg2, not asyncpg. Accept whatever they give us and adapt it rather than making
        deploy-time config a source of copy-paste errors.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        # asyncpg takes SSL as a connect kwarg (see app.core.database), not a URL query param.
        url = re.sub(r"[?&]sslmode=[^&]*", "", url)
        return url

# Instantiate settings to expose to the rest of the application
settings = Settings()
