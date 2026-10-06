from httpx import AsyncClient

from tests.conftest import API, PASSWORD, UserFactory, auth_headers


async def test_register(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "New.User@Example.com", "password": PASSWORD, "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["is_superuser"] is False
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_conflicts(
    client: AsyncClient, create_user: UserFactory
) -> None:
    await create_user("taken@example.com")
    response = await client.post(
        f"{API}/auth/register", json={"email": "TAKEN@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_register_validation_error(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/register", json={"email": "not-an-email", "password": "short"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {tuple(d["loc"]) for d in error["details"]} == {
        ("body", "email"),
        ("body", "password"),
    }


async def test_login_and_me(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("me@example.com")
    headers = await auth_headers(client, "me@example.com")

    response = await client.get(f"{API}/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_login_wrong_password(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("me@example.com")
    response = await client.post(
        f"{API}/auth/login", data={"username": "me@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/login", data={"username": "ghost@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/auth/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"] == {
        "code": "unauthorized",
        "message": "Not signed in",
        "details": None,
        "request_id": response.headers["X-Request-ID"],
    }


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
