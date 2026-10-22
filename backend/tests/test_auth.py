import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.auth import SESSION_COOKIE, create_session_token, hash_password
from app.config import get_settings
from app.main import app
from app.models import User
from app.schemas import CurrentUser

EMAIL = "pat@example.com"
PASSWORD = "correct horse battery staple"


def get_me(token: str | None = None):
    client = TestClient(app)
    if token is not None:
        client.cookies.set(SESSION_COOKIE, token)
    return client.get("/api/auth/me")


def claims(**overrides) -> dict:
    return {
        "sub": str(uuid.uuid4()),
        "email": EMAIL,
        "name": "Pat",
        "role": "analyst",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **overrides,
    }


def sign(payload: dict, secret: str | None = None) -> str:
    return jwt.encode(payload, secret or get_settings().jwt_secret, algorithm="HS256")


def add_user(db, *, password: str | None = PASSWORD, role: str = "analyst") -> None:
    db.execute(
        insert(User).values(
            email=EMAIL,
            display_name="Pat",
            role=role,
            password_hash=hash_password(password) if password else None,
        )
    )


# get_current_user (no database needed: identity and role come from the token alone)


def test_no_token_returns_401():
    assert get_me().status_code == 401


@pytest.mark.parametrize("role", ["analyst", "manager", "admin"])
def test_role_comes_from_the_token(role):
    user = CurrentUser(id=uuid.uuid4(), email=EMAIL, display_name="Pat", role=role)

    response = get_me(create_session_token(user))

    assert response.status_code == 200
    assert response.json() == user.model_dump(mode="json")


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("not-a-jwt", id="garbage"),
        pytest.param(sign(claims(exp=datetime.now(UTC) - timedelta(minutes=1))), id="expired"),
        pytest.param(sign(claims(), "some-other-secret-that-is-32-chars-long"), id="wrong-secret"),
        pytest.param(jwt.encode(claims(), None, algorithm="none"), id="unsigned"),
        pytest.param(sign(claims(role="superuser")), id="unknown-role"),
        pytest.param(sign({k: v for k, v in claims().items() if k != "exp"}), id="no-expiry"),
    ],
)
def test_invalid_tokens_return_401(token):
    assert get_me(token).status_code == 401


# Login and logout (database)


def test_login_sets_an_httponly_session_cookie(client, db):
    add_user(db, role="manager")

    response = client.post(
        "/api/auth/login", json={"email": "Pat@Example.com ", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "manager"
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert client.get("/api/auth/me").json() == response.json()


@pytest.mark.parametrize(
    ("email", "password"),
    [(EMAIL, "wrong password"), ("nobody@example.com", PASSWORD)],
    ids=["wrong-password", "unknown-email"],
)
def test_login_rejects_bad_credentials(client, db, email, password):
    add_user(db)

    response = client.post("/api/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_user_without_a_password_cannot_log_in(client, db):
    add_user(db, password=None)

    response = client.post("/api/auth/login", json={"email": EMAIL, "password": ""})

    assert response.status_code == 401


def test_logout_ends_the_session(client, db):
    add_user(db)
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
