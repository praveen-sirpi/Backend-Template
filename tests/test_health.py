from httpx import AsyncClient

from src.main import app


async def test_root_returns_app_info(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["environment"] == "test"


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "disabled"}}


async def test_request_id_is_generated(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32


async def test_valid_incoming_request_id_is_propagated(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "trace-abc.123"})
    assert response.headers["X-Request-ID"] == "trace-abc.123"


async def test_unsafe_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert response.headers["X-Request-ID"] != "bad id\nwith newline"


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_unhandled_exception_returns_json_500(client: AsyncClient) -> None:
    async def boom() -> None:
        raise RuntimeError("kaboom")

    app.add_api_route("/__test_boom", boom)
    response = await client.get("/__test_boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "kaboom" not in response.text  # internals are never leaked to clients
