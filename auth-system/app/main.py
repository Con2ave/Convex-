import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core import security
from app.core.database import get_async_db, async_session_maker
from app.api.auth import router as auth_router
from app.api.users import user_router, admin_router
from app.api.study_sessions import router as study_sessions_router
from app.api.rewards import router as rewards_router
from app.api.subscriptions import router as subscriptions_router
from app.core.limiter import limiter
from app import crud

# Setup structured logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Seeding the database with user admin on startup
async def seed_database() -> None:
    logger.info("Verifying initial seeding...")
    async with async_session_maker() as db:
        admin_user = await crud.user.get_user_by_email(db, settings.ADMIN_EMAIL)
        if not admin_user:
            logger.info("No admin user detected. Seeding initial system administrator...")
            hashed_pwd = security.get_password_hash(settings.ADMIN_PASSWORD)
            await crud.user.create_admin_user(
                db=db,
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hashed_pwd
            )
            logger.info(f"Seeded admin user successfully: {settings.ADMIN_EMAIL}")
        else:
            logger.info("Admin user already successfully configured in the database.")


# Modern lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check/run seeding on application start
    try:
        await seed_database()
    except Exception as e:
        logger.error(f"Error seeding initial database state: {e}")
    yield
    # Shutdown / cleanup steps go here if needed


# Instantiate app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="ConVex API - study session tracking, anti-cheat verification, and a points rewards engine.",
    version="1.0.0",
    lifespan=lifespan
)

# Throttling integration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS (Cross-Origin Resource Sharing) - locked to the configured frontend origin(s),
# set via the ALLOWED_ORIGINS env var (comma-separated for previews/multiple deployments).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard error handler for generic exceptions (Prevents internal stack leak)
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled system exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred. Please try again later."},
    )

# Include API Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(study_sessions_router)
app.include_router(rewards_router)
app.include_router(subscriptions_router)

# Healthcheck base endpoint
@app.get("/health", tags=["Utilities"])
@limiter.limit("30/minute")
async def health_check(request: Request):
    """Utility endpoint to verify application operational state."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}
