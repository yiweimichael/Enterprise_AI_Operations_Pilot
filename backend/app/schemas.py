"""Pydantic request and response models shared with the frontend via OpenAPI."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["analyst", "manager", "admin"]


class LoginRequest(BaseModel):
    email: str
    # Bounded so a huge password cannot make hashing expensive.
    password: str = Field(max_length=256)


class CurrentUser(BaseModel):
    """The signed-in user, as carried in the session token."""

    id: uuid.UUID
    email: str
    display_name: str
    role: Role
