"""Schémas Pydantic (validation des entrées/sorties de l'API)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


# --- Sorties ---------------------------------------------------------------
class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Entrées ---------------------------------------------------------------
class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class RoleUpdate(BaseModel):
    role: UserRole


class ActiveUpdate(BaseModel):
    is_active: bool


# --- Repli auth locale -----------------------------------------------------
class LocalRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)


class LocalLogin(BaseModel):
    email: EmailStr
    password: str
