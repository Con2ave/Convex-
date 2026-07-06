import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator, ConfigDict

# Regular expression for strong password verification
# - 8+ characters
# - At least 1 uppercase letter
# - At least 1 lowercase letter
# - At least 1 digit
# - At least 1 special character
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
)

def validate_password_strength(password: str) -> str:
    """Helper to enforce high-entropy passwords."""
    if not PASSWORD_REGEX.match(password):
        raise ValueError(
            "Password must be at least 8 characters long and contain at "
            "least one uppercase letter, one lowercase letter, one digit, "
            "and one special character (@$!%*?&)."
        )
    return password


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="User's email address")


class UserRegister(UserBase):
    password: str = Field(..., min_length=8, description="Cryptographically strong password")
    password_confirm: str = Field(..., description="Confirm password must match password")

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "UserRegister":
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match.")
        return self


class UserLogin(BaseModel):
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(None)


class UserChangePassword(BaseModel):
    current_password: str = Field(..., description="Current login password")
    new_password: str = Field(..., min_length=8, description="New strong password")
    new_password_confirm: str = Field(..., description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "UserChangePassword":
        if self.new_password != self.new_password_confirm:
            raise ValueError("New passwords do not match.")
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Verified or registered email address")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset JWT token")
    new_password: str = Field(..., min_length=8, description="New strong password")
    new_password_confirm: str = Field(..., description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def check_new_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("Passwords do not match.")
        return self


# Token Schemas
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str
