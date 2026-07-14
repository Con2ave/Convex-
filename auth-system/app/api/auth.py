from fastapi import APIRouter, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.schemas.user import (
    UserRegister,
    UserLogin,
    TokenResponse,
    TokenRefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse
)
from app.services import auth as auth_service
from app.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_in: UserRegister,
    db: AsyncSession = Depends(get_async_db)
):
    """Register a new user account. Returns the created user details."""
    new_user = await auth_service.register_user(db=db, user_in=user_in)
    return new_user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db)
):
    """Authenticate via username/email and password, returning access and refresh JWTs.
    
    Compatible with Swagger client OAuth2 flow.
    """
    user_login = UserLogin(username=form_data.username, password=form_data.password)
    user = await auth_service.authenticate_user(db=db, login_in=user_login)
    tokens = await auth_service.issue_tokens(db=db, user=user)
    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    token_in: TokenRefreshRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Logout user by invalidating/revoking their supplied JWT refresh token."""
    await auth_service.logout_user(db=db, refresh_token=token_in.refresh_token)
    return {"detail": "Successfully logged out."}


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    token_in: TokenRefreshRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Rotate user refresh token and return a fresh access + refresh token set."""
    tokens = await auth_service.refresh_access_token(db=db, refresh_token=token_in.refresh_token)
    return tokens


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    forgot_in: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Initiate password verification reset. Generates email verification links (Mocked)."""
    await auth_service.forgot_password(db=db, email=forgot_in.email)
    return {
        "detail": "If the email is registered in our system, a password reset link has been sent."
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    reset_in: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """Reset user password using token received from forgot-password flow."""
    await auth_service.reset_password(db=db, reset_in=reset_in)
    return {"detail": "Password has been successfully reset."}


@router.get("/verify-email", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def verify_email(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Verify registration email address using the token sent to the user's inbox."""
    await auth_service.verify_email_token(db=db, token=token)
    return {"detail": "Email address successfully verified."}
