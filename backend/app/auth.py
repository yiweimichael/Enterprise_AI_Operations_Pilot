"""Sign-in: password login, a JWT in an httpOnly cookie, and the get_current_user dependency.

The user's identity and role come only from the signed session token, never from the
request body or the chat, so every permission check downstream can trust them.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import APIKeyCookie
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import CurrentUser, LoginRequest

SESSION_COOKIE = "session"
JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()
# Checked when the email is unknown, so a failed login takes the same time either way.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe())
# auto_error=False so a missing cookie gets our 401 rather than FastAPI's default.
_session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """False for a wrong password, and for users who have no password set."""
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def create_session_token(user: CurrentUser) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.display_name,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail)


def get_current_user(token: Annotated[str | None, Depends(_session_cookie)]) -> CurrentUser:
    """The signed-in user from the session cookie; 401 when it is missing or invalid."""
    if token is None:
        raise _unauthorized("Not signed in")
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            # Pinned so a token cannot choose its own algorithm (for example "none").
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "role", "exp"]},
        )
        return CurrentUser(
            id=claims["sub"],
            email=claims["email"],
            display_name=claims["name"],
            role=claims["role"],
        )
    except (jwt.InvalidTokenError, KeyError, ValidationError):
        raise _unauthorized("Invalid or expired session") from None


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Annotated[Session, Depends(get_db)]
) -> CurrentUser:
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not verify_password(body.password, user.password_hash if user else None):
        raise _unauthorized("Incorrect email or password")

    current_user = CurrentUser.model_validate(user, from_attributes=True)
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(current_user),
        max_age=settings.session_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


@router.get("/me")
def me(user: CurrentUserDep) -> CurrentUser:
    return user
