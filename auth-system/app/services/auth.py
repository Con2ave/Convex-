import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.config import settings
from app import crud
from app.core import security
from app.models.user import User, UserRefreshToken
from app.schemas.user import UserRegister, UserLogin, TokenResponse, ResetPasswordRequest
from app.services import email as email_service

logger = logging.getLogger(__name__)

async def send_verification_email(email: str) -> None:
    """Generate a fresh verification token and email it. Public (not a leading-underscore
    helper) since app.api.users' re-verify-on-email-change flow needs the exact same behavior -
    kept in one place rather than duplicated."""
    token = security.create_email_verification_token(email)
    link = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"
    try:
        await email_service.send_email(
            to=email,
            subject="Verify your ConVex email address",
            body=(
                "Welcome to ConVex! Verify your email address to get started:\n\n"
                f"{link}\n\n"
                f"This link expires in {settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS} hours."
            ),
        )
    except email_service.EmailSendError:
        pass  # already logged inside send_email - never fail the caller's request over this


async def register_user(db: AsyncSession, user_in: UserRegister) -> User:
    """Register a new user after validating username and email uniqueness."""
    # Check if username already exists
    existing_username = await crud.user.get_user_by_username(db, user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered."
        )

    # Check if email already exists
    existing_email = await crud.user.get_user_by_email(db, user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered."
        )

    # Proceed to create the user
    new_user = await crud.user.create_user(db, user_in)
    logger.info(f"Registered new user: {new_user.username} (ID: {new_user.id})")

    await send_verification_email(new_user.email)

    return new_user


async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> User:
    """Authenticate user with username or email, verify password hash, and track last login."""
    # Try fetching by username
    user = await crud.user.get_user_by_username(db, login_in.username)
    if not user:
        # Try fetching by email instead
        user = await crud.user.get_user_by_email(db, login_in.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated."
        )

    # Check password
    if not security.verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Record last login timestamp
    await crud.user.update_last_login(db, user)
    logger.info(f"User {user.username} authenticated successfully.")
    return user


async def issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    """Issue a new Access Token and Refresh Token pair, and persist the Refresh Token in the DB."""
    # Access Token (short-lived)
    access_token = security.create_access_token(subject=user.id)
    
    # Refresh Token (long-lived)
    refresh_token = security.create_refresh_token(subject=user.id)
    
    # Calculate expiry
    expires_in_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    
    # Save the refresh token in the database
    await crud.user.create_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=expires_at
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Validate a Refresh Token, revoke it, and issue a fresh token pair (Refresh Token Rotation)."""
    try:
        # Decode and verify refresh signature
        payload = security.decode_token(refresh_token, settings.JWT_REFRESH_SECRET_KEY)
        scope = payload.get("scope")
        if scope != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token scope.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve refresh token from DB
    db_token = await crud.user.get_refresh_token(db, refresh_token)
    if not db_token or db_token.is_revoked:
        # Security Alert: Could be a reuse of a revoked token
        logger.warning(f"Potential refresh token reuse attack detected for user ID: {user_id}!")
        if db_token:
            # Revoke all tokens for this user for security reasons
            await crud.user.revoke_all_user_tokens(db, user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token expiration
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user
    user = await crud.user.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated or deleted.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke current refresh token (Rotation)
    await crud.user.revoke_refresh_token(db, db_token)
    
    # Issue a brand new pair of tokens
    new_tokens = await issue_tokens(db, user)
    logger.info(f"Rotated refresh token for user {user.username} (ID: {user.id})")
    return new_tokens


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    """Invalidate a specific Refresh Token on logout."""
    db_token = await crud.user.get_refresh_token(db, refresh_token)
    if db_token:
        await crud.user.revoke_refresh_token(db, db_token)
        logger.info(f"User refresh session revoked on logout. user_id: {db_token.user_id}")


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Handle password reset generation. Suppresses User Not Found errors to prevent enumeration."""
    user = await crud.user.get_user_by_email(db, email)
    if not user:
        # Silent success to prevent email enumeration
        logger.info(f"Forgot password requested for non-existent email {email}.")
        return

    reset_token = security.create_password_reset_token(user.email)
    link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={reset_token}"
    try:
        await email_service.send_email(
            to=user.email,
            subject="Reset your ConVex password",
            body=(
                "Someone requested a password reset for your ConVex account. "
                f"If this was you, reset your password here:\n\n{link}\n\n"
                f"This link expires in {settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS} hours. "
                "If you didn't request this, you can safely ignore this email."
            ),
        )
    except email_service.EmailSendError:
        pass


async def reset_password(db: AsyncSession, reset_in: ResetPasswordRequest) -> None:
    """Verify reset token and update user password. Revokes active refresh tokens for sanity."""
    email = security.verify_scoped_token(reset_in.token, "password_reset")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token."
        )

    user = await crud.user.get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found or deactivated."
        )

    # Hash new password
    hashed_password = security.get_password_hash(reset_in.new_password)
    
    # Update password
    await crud.user.update_user_password(db, user, hashed_password)
    
    # SECURITY: Revoke all other ongoing login sessions (Refresh Tokens) for this user
    await crud.user.revoke_all_user_tokens(db, user.id)
    
    logger.info(f"Successfully reset password for user {user.username} (ID: {user.id}).")


async def verify_email_token(db: AsyncSession, token: str) -> None:
    """Verify user email path via email scoped verification token."""
    email = security.verify_scoped_token(token, "email_verification")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token."
        )

    user = await crud.user.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.is_verified:
        logger.info(f"User {user.username} is already verified.")
        return

    await crud.user.verify_user(db, user)
    logger.info(f"User {user.username} email ({user.email}) verified.")
