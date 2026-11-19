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


class Passage(BaseModel):
    """A retrieved document chunk and its exact location in the source, for citations."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    source: str
    section: str | None
    page: int | None
    # Character offsets into the source file: file_text[start_char:end_char] == content.
    start_char: int
    end_char: int
    content: str
    # Cosine similarity to the query, from -1 to 1; higher is closer.
    similarity: float
