from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hashed value."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate a password hash using bcrypt."""
    # bcrypt.gensalt() generates a secure salt by default
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

import uuid

def create_jwt_token(
    subject: str | int,
    expires_delta: timedelta,
    secret_key: str,
    scope: str = "access"
) -> str:
    """Create a signed JWT token with a given subject and scope."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    to_encode = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "scope": scope,
        "jti": uuid.uuid4().hex
    }
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_access_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    """Generate an Access Token for a user."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_jwt_token(
        subject=subject,
        expires_delta=expires_delta,
        secret_key=settings.JWT_SECRET_KEY,
        scope="access"
    )

def create_refresh_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a Refresh Token for a user."""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_jwt_token(
        subject=subject,
        expires_delta=expires_delta,
        secret_key=settings.JWT_REFRESH_SECRET_KEY,
        scope="refresh"
    )

def create_password_reset_token(email: str) -> str:
    """Generate a stateless, scoped Password Reset Token."""
    expires_delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    return create_jwt_token(
        subject=email,
        expires_delta=expires_delta,
        secret_key=settings.JWT_SECRET_KEY,
        scope="password_reset"
    )

def create_email_verification_token(email: str) -> str:
    """Generate a stateless, scoped Email Verification Token."""
    expires_delta = timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)
    return create_jwt_token(
        subject=email,
        expires_delta=expires_delta,
        secret_key=settings.JWT_SECRET_KEY,
        scope="email_verification"
    )

def decode_token(token: str, secret_key: str) -> Dict[str, Any]:
    """Decode a JWT and return its claims. Raises JWTError if invalid or expired."""
    return jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])

def verify_scoped_token(token: str, expected_scope: str) -> Optional[str]:
    """Verify a token's validity and ensure it matches the expected scope.
    
    Returns the subject (sub) claim (e.g., email or user_id) if valid, otherwise None.
    """
    try:
        payload = decode_token(token, settings.JWT_SECRET_KEY)
        scope = payload.get("scope")
        if scope != expected_scope:
            return None
        subject = payload.get("sub")
        return str(subject) if subject else None
    except JWTError:
        return None
