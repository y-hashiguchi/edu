"""Auth DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    # Sprint 7: course selection is mandatory at registration. The
    # actual slug-existence check happens in the auth route — a
    # Pydantic-level enum would create a circular import.
    course_slug: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime
    # Surfacing the admin flag here lets the SPA route /admin views via a
    # plain getter on the auth store. It is NOT used as the RBAC source
    # of truth — server-side endpoints enforce is_admin again on every
    # admin-only call.
    is_admin: bool = False

    model_config = {"from_attributes": True}
