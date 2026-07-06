from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core import security
from app.core.database import get_async_db
from app import crud
from app.models.user import User

# OAuth2 Password Bearer flow. Points to the login endpoint.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    auto_error=True
)

async def get_current_user(
    db: AsyncSession = Depends(get_async_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Dependency to extract, decode and validate the Access Token and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode token with Access Token secret
        payload = security.decode_token(token, settings.JWT_SECRET_KEY)
        user_id_str: str = payload.get("sub")
        scope: str = payload.get("scope")
        
        # Ensure correct scope is configured
        if scope != "access" or not user_id_str:
            raise credentials_exception
            
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    # Retrieve user from database
    user = await crud.user.get_user_by_id(db, user_id)
    if not user:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated."
        )
        
    return user


class RoleChecker:
    """Dependency factory class to enforce Role-Based Access Control (RBAC)."""
    
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """Evaluate if the authenticated user has one of the allowed roles."""
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have sufficient permissions to perform this action."
            )
        return current_user

# Predefined dependencies for common access control scenarios
get_admin_user = RoleChecker(allowed_roles=["admin"])
get_any_active_user = RoleChecker(allowed_roles=["admin", "user"])
