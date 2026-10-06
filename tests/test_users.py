from httpx import AsyncClient

from tests.conftest import API, UserFactory, auth_headers


async def test_list_users_requires_superuser(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("regular@example.com")
    headers = await auth_headers(client, "regular@example.com")

    response = await client.get(f"{API}/users", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_list_users_paginates(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("admin@example.com", is_superuser=True)
    for i in range(3):
        await create_user(f"user{i}@example.com")
    headers = await auth_headers(client, "admin@example.com")

    response = await client.get(f"{API}/users", params={"limit": 2, "offset": 1}, headers=headers)
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 4
    assert page["limit"] == 2
    assert page["offset"] == 1
    assert len(page["items"]) == 2


async def test_pagination_limit_is_validated(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("admin@example.com", is_superuser=True)
    headers = await auth_headers(client, "admin@example.com")

    response = await client.get(f"{API}/users", params={"limit": 1000}, headers=headers)
    assert response.status_code == 422


async def test_update_me(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("me@example.com")
    headers = await auth_headers(client, "me@example.com")

    response = await client.patch(
        f"{API}/users/me",
        json={"full_name": "Renamed", "password": "a-brand-new-password"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed"

    # The new password works.
    await auth_headers(client, "me@example.com", "a-brand-new-password")


async def test_get_user_permissions(client: AsyncClient, create_user: UserFactory) -> None:
    alice = await create_user("alice@example.com")
    bob = await create_user("bob@example.com")
    headers = await auth_headers(client, "alice@example.com")

    assert (await client.get(f"{API}/users/{alice.id}", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/users/{bob.id}", headers=headers)).status_code == 403


async def test_get_missing_user(client: AsyncClient, create_user: UserFactory) -> None:
    await create_user("admin@example.com", is_superuser=True)
    headers = await auth_headers(client, "admin@example.com")

    response = await client.get(
        f"{API}/users/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "User not found"
