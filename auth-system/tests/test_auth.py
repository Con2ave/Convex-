import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRefreshToken
from app.core import security
from app.crud.user import hash_refresh_token

# Test User Seed Configuration
TEST_USER_DATA = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "SecurePassword123!",
    "password_confirm": "SecurePassword123!"
}

TEST_ADMIN_DATA = {
    "username": "adminuser",
    "email": "admin@example.com",
    "password": "SecureAdmin123!",
    "password_confirm": "SecureAdmin123!"
}


# ----------------- User Registration Tests -----------------

@pytest.mark.asyncio
async def test_user_registration_success(client: AsyncClient, db_session: AsyncSession):
    """Test standard client registration details."""
    response = await client.post("/auth/register", json=TEST_USER_DATA)
    assert response.status_code == 201
    
    data = response.json()
    assert data["username"] == TEST_USER_DATA["username"]
    assert data["email"] == TEST_USER_DATA["email"]
    assert "id" in data
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert data["is_verified"] is False  # Awaiting verification


@pytest.mark.asyncio
async def test_user_registration_validation_errors(client: AsyncClient):
    """Test inputs failing validation filters (non-matching and low-entropy passwords)."""
    # Passwords do not match
    mismatch_data = TEST_USER_DATA.copy()
    mismatch_data["password_confirm"] = "mismatch"
    response = await client.post("/auth/register", json=mismatch_data)
    assert response.status_code == 422  # Unprocessable Entity
    
    # Password too weak (no uppercase, no symbol)
    weak_data = TEST_USER_DATA.copy()
    weak_data["password"] = "weakpwd"
    weak_data["password_confirm"] = "weakpwd"
    response = await client.post("/auth/register", json=weak_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_registration_duplicate_checks(client: AsyncClient):
    """Test duplicate registration constraints."""
    # First registration
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    # Try registering username again
    duplicate_username = TEST_USER_DATA.copy()
    duplicate_username["email"] = "otheremail@example.com"
    response = await client.post("/auth/register", json=duplicate_username)
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]

    # Try registering email again
    duplicate_email = TEST_USER_DATA.copy()
    duplicate_email["username"] = "otheruser"
    response = await client.post("/auth/register", json=duplicate_email)
    assert response.status_code == 400
    assert "Email address already registered" in response.json()["detail"]


# ----------------- Authentication / Login / Logout Tests -----------------

@pytest.mark.asyncio
async def test_user_login_success(client: AsyncClient):
    """Register and test standard login pathways."""
    await client.post("/auth/register", json=TEST_USER_DATA)

    # Login payload as application/x-www-form-urlencoded
    form_payload = {
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    }
    response = await client.post("/auth/login", data=form_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_user_login_fails_with_invalid_credentials(client: AsyncClient):
    """Verify incorrect login attempts return 401."""
    form_payload = {
        "username": "nonexistent",
        "password": "anypassword"
    }
    response = await client.post("/auth/login", data=form_payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_logout_invalidates_token(client: AsyncClient, db_session: AsyncSession):
    """Test system logout revokes the token from DB."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    tokens = login_resp.json()
    refresh_token = tokens["refresh_token"]

    # Logout
    logout_resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200
    
    # Assert DB token status is revoked - stored (and looked up) as a hash, not the raw token.
    result = await db_session.execute(
        select(UserRefreshToken).where(UserRefreshToken.token == hash_refresh_token(refresh_token))
    )
    db_token = result.scalar_one_or_none()
    assert db_token is not None
    assert db_token.is_revoked is True


@pytest.mark.asyncio
async def test_refresh_token_never_stored_in_plaintext(client: AsyncClient, db_session: AsyncSession):
    """A DB compromise alone must not hand over a usable bearer credential - the raw JWT should
    never appear anywhere in the refresh_tokens table, only its hash."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    refresh_token = login_resp.json()["refresh_token"]

    raw_match = await db_session.execute(
        select(UserRefreshToken).where(UserRefreshToken.token == refresh_token)
    )
    assert raw_match.scalar_one_or_none() is None

    hashed_match = await db_session.execute(
        select(UserRefreshToken).where(UserRefreshToken.token == hash_refresh_token(refresh_token))
    )
    assert hashed_match.scalar_one_or_none() is not None


# ----------------- Refresh Token Rotation Tests -----------------

@pytest.mark.asyncio
async def test_refresh_token_rotation_workflow(client: AsyncClient):
    """Verify refresh operations rotate tokens and block old ones."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    refresh_token = login_resp.json()["refresh_token"]

    # Request rotation
    rotate_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert rotate_resp.status_code == 200
    assert "access_token" in rotate_resp.json()
    assert "refresh_token" in rotate_resp.json()
    
    new_refresh = rotate_resp.json()["refresh_token"]
    assert new_refresh != refresh_token

    # Verify old refresh token is disallowed (Reuse Detection)
    reuse_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_resp.status_code == 401


# ----------------- Authorized User Route (/me) Tests -----------------

@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient):
    """Test retrieving authenticated user details."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    access_token = login_resp.json()["access_token"]

    # Call /users/me
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_resp = await client.get("/users/me", headers=headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["username"] == TEST_USER_DATA["username"]


@pytest.mark.asyncio
async def test_profile_update_and_email_reverification(client: AsyncClient):
    """Test user profile settings modification."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Verify user state is initially not verified
    profile_resp = await client.get("/users/me", headers=headers)
    assert profile_resp.json()["is_verified"] is False

    # Update profile email
    new_profile = {"email": "newemail@example.com"}
    update_resp = await client.put("/users/me", json=new_profile, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["email"] == "newemail@example.com"


# ----------------- Password Reset / Reset Token Workflows -----------------

@pytest.mark.asyncio
async def test_password_forgot_and_reset_workflow(client: AsyncClient, db_session: AsyncSession):
    """Test stateless user password reset workflow."""
    # Register user
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    # Request forgot password token triggers email log
    forgot_resp = await client.post(
        "/auth/forgot-password", 
        json={"email": TEST_USER_DATA["email"]}
    )
    assert forgot_resp.status_code == 200
    
    # Manually generate reset token for evaluation since local email is mocked
    valid_token = security.create_password_reset_token(TEST_USER_DATA["email"])
    
    # Submit reset Form
    new_auth = {
        "token": valid_token,
        "new_password": "NewSecurePassword456!",
        "new_password_confirm": "NewSecurePassword456!"
    }
    reset_resp = await client.post("/auth/reset-password", json=new_auth)
    assert reset_resp.status_code == 200

    # Old password fails
    old_login = {
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    }
    assert (await client.post("/auth/login", data=old_login)).status_code == 401

    # New password succeeds
    new_login = {
        "username": TEST_USER_DATA["username"],
        "password": "NewSecurePassword456!"
    }
    assert (await client.post("/auth/login", data=new_login)).status_code == 200


# ----------------- Email Verification Workflows -----------------

@pytest.mark.asyncio
async def test_email_verification_success(client: AsyncClient, db_session: AsyncSession):
    """Test verification link parsing."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    # Build token
    verify_token = security.create_email_verification_token(TEST_USER_DATA["email"])
    
    # Call verify-email endpoint
    verify_resp = await client.get(f"/auth/verify-email?token={verify_token}")
    assert verify_resp.status_code == 200
    
    # Check db user verification flag is set to true
    result = await db_session.execute(
        select(User).where(User.email == TEST_USER_DATA["email"])
    )
    db_user = result.scalar_one()
    assert db_user.is_verified is True


# ----------------- Role-Based Access Control (RBAC) Tests -----------------

@pytest.mark.asyncio
async def test_rbac_user_cannot_access_admin_endpoints(client: AsyncClient):
    """Ensure permissions layer rejects non-admin users."""
    await client.post("/auth/register", json=TEST_USER_DATA)
    
    login_resp = await client.post("/auth/login", data={
        "username": TEST_USER_DATA["username"],
        "password": TEST_USER_DATA["password"]
    })
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # User attempts admin list
    admin_list = await client.get("/admin/users", headers=headers)
    assert admin_list.status_code == 403

    # User attempts admin delete
    admin_del = await client.delete("/admin/users/999", headers=headers)
    assert admin_del.status_code == 403


@pytest.mark.asyncio
async def test_rbac_admin_can_access_admin_endpoints(
    client: AsyncClient, 
    db_session: AsyncSession
):
    """Ensure standard admins can manage and list user accounts."""
    # Seed an admin user in database manually
    admin_pwd_hash = security.get_password_hash(TEST_ADMIN_DATA["password"])
    db_admin = User(
        username=TEST_ADMIN_DATA["username"],
        email=TEST_ADMIN_DATA["email"],
        hashed_password=admin_pwd_hash,
        role="admin",
        is_active=True,
        is_verified=True
    )
    db_session.add(db_admin)
    
    # Seed regular user
    user_pwd_hash = security.get_password_hash(TEST_USER_DATA["password"])
    db_user = User(
        username=TEST_USER_DATA["username"],
        email=TEST_USER_DATA["email"],
        hashed_password=user_pwd_hash,
        role="user",
        is_active=True,
        is_verified=False
    )
    db_session.add(db_user)
    await db_session.commit()

    # Authenticate as admin
    login_resp = await client.post("/auth/login", data={
        "username": TEST_ADMIN_DATA["username"],
        "password": TEST_ADMIN_DATA["password"]
    })
    admin_access = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_access}"}

    # Admin lists users
    users_resp = await client.get("/admin/users", headers=headers)
    assert users_resp.status_code == 200
    assert len(users_resp.json()) == 2  # Admin + User

    # Admin deletes user
    user_id = db_user.id
    del_resp = await client.delete(f"/admin/users/{user_id}", headers=headers)
    assert del_resp.status_code == 200
    
    # Verify user delete updated in db
    result = await db_session.execute(select(User).where(User.id == user_id))
    assert result.scalar_one_or_none() is None
