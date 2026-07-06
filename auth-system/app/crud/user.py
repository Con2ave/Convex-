from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRefreshToken
from app.schemas.user import UserRegister, UserUpdate
from app.core.security import get_password_hash

# ----------------- User CRUD Operations -----------------

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Retrieve a user by their unique primary key integer ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Retrieve a user by their unique username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Retrieve a user by their unique email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """Retrieve a paginated list of users."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())

async def create_user(db: AsyncSession, user_in: UserRegister) -> User:
    """Create a new user in the database, hashing their password pre-insert."""
    hashed_pwd = get_password_hash(user_in.password)
    
    # We default the first registered user to admin if database is empty,
    # or rely on normal 'user' default. Here we just read role default ("user")
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_pwd,
        role="user",
        is_active=True,
        is_verified=False
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def create_admin_user(db: AsyncSession, username: str, email: str, password_hash: str) -> User:
    """Insert or retrieve a superuser directly (generally used for initial admin seeding)."""
    db_user = User(
        username=username,
        email=email,
        hashed_password=password_hash,
        role="admin",
        is_active=True,
        is_verified=True
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, db_user: User, user_in: UserUpdate | dict) -> User:
    """Update user account metadata (e.g. username/email)."""
    update_data = user_in if isinstance(user_in, dict) else user_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Hard delete a user from the system."""
    result = await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return (result.rowcount or 0) > 0

async def update_last_login(db: AsyncSession, db_user: User) -> User:
    """Track the exact timestamp a user authenticated successfully."""
    db_user.last_login = datetime.now(timezone.utc)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user_password(db: AsyncSession, db_user: User, hashed_pass: str) -> User:
    """Directly replace a user's password hash in the database."""
    db_user.hashed_password = hashed_pass
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def verify_user(db: AsyncSession, db_user: User) -> User:
    """Mark user account as email-verified."""
    db_user.is_verified = True
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# ----------------- Refresh Token CRUD Operations -----------------

async def create_refresh_token(
    db: AsyncSession, 
    user_id: int, 
    token: str, 
    expires_at: datetime
) -> UserRefreshToken:
    """Link a newly issued JWT Refresh Token to the user in database."""
    db_token = UserRefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)
    return db_token

async def get_refresh_token(db: AsyncSession, token: str) -> Optional[UserRefreshToken]:
    """Look up a stored Refresh Token instance."""
    result = await db.execute(select(UserRefreshToken).where(UserRefreshToken.token == token))
    return result.scalar_one_or_none()

async def revoke_refresh_token(db: AsyncSession, db_token: UserRefreshToken) -> None:
    """Revoke a specific refresh token (marking session invalid)."""
    db_token.is_revoked = True
    db.add(db_token)
    await db.commit()

async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> None:
    """Revoke all active refresh sessions linked to a user (force global user logout)."""
    await db.execute(
        update(UserRefreshToken)
        .where(UserRefreshToken.user_id == user_id)
        .values(is_revoked=True)
    )
    await db.commit()
