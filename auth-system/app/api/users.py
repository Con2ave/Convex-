import logging
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import get_current_user, get_admin_user
from app.schemas.user import UserResponse, UserUpdate, UserChangePassword
from app.models.user import User
from app.core import security
from app import crud

logger = logging.getLogger(__name__)

# Double router definition for routing modularity
user_router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(prefix="/admin", tags=["Admin User Management"])


# ----------------- User Profile Endpoints -----------------

@user_router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user session."""
    return current_user


@user_router.put("/me", response_model=UserResponse)
async def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update profile details (username, email) for the current user."""
    # Validate uniqueness constraints if changing username
    if user_in.username and user_in.username != current_user.username:
        existing = await crud.user.get_user_by_username(db, user_in.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already in use."
            )

    # Validate uniqueness constraints if changing email
    email_changed = False
    if user_in.email and user_in.email != current_user.email:
        existing = await crud.user.get_user_by_email(db, user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use."
            )
        email_changed = True

    # Perform user update
    updated_user = await crud.user.update_user(db, current_user, user_in)
    
    # If email changed, default is_verified back to False and mock verify re-trigger
    if email_changed:
        updated_user.is_verified = False
        db.add(updated_user)
        await db.commit()
        await db.refresh(updated_user)
        
        verification_token = security.create_email_verification_token(updated_user.email)
        logger.warning(
            f"[MOCK EMAIL SERVICE] Re-verification email sent to changed address {updated_user.email}. "
            f"Token: {verification_token}"
        )
        
    return updated_user


@user_router.put("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    pass_in: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Change current login password securely, invalidating active refresh sessions."""
    # Verify current password matches
    if not security.verify_password(pass_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )

    # Prevent password reuse
    if pass_in.current_password == pass_in.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current password."
        )

    # Update password hash in db
    new_hashed = security.get_password_hash(pass_in.new_password)
    await crud.user.update_user_password(db, current_user, new_hashed)
    
    # Revoke all refresh tokens to terminate sessions on other clients
    await crud.user.revoke_all_user_tokens(db, current_user.id)
    
    return {"detail": "Password successfully updated. Other active sessions have been signed out."}


# ----------------- Admin Endpoints -----------------

@admin_router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Admin-only endpoint to list all registered users."""
    users = await crud.user.get_users(db, skip=skip, limit=limit)
    return users


@admin_router.delete("/users/{id}", status_code=status.HTTP_200_OK)
async def delete_user(
    id: int,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Admin-only endpoint to delete a user account from database."""
    # Prevent self deletion
    if id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own account."
        )

    user_exists = await crud.user.get_user_by_id(db, id)
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    await crud.user.delete_user(db, id)
    logger.info(f"Admin (ID: {current_admin.id}) deleted user ID: {id}")
    return {"detail": f"User with ID {id} has been successfully deleted."}
