import logging

from fastapi import APIRouter, Response, status

from src.core.config import settings
from src.db.session import db
from src.providers.cache import cache
from src.schemas.health import AppInfo, CheckStatus, HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/", response_model=AppInfo, summary="Service info")
async def root() -> AppInfo:
    return AppInfo(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        docs="/docs" if settings.docs_enabled else None,
    )


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (checks dependencies)",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is down"}},
)
async def readiness(response: Response) -> ReadinessResponse:
    checks: dict[str, CheckStatus] = {}

    try:
        await db.ping()
        checks["database"] = "ok"
    except Exception:
        logger.exception("Readiness check failed: database")
        checks["database"] = "error"

    if cache.enabled:
        checks["redis"] = "ok" if await cache.ping() else "error"
    else:
        checks["redis"] = "disabled"

    healthy = "error" not in checks.values()
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if healthy else "degraded", checks=checks)
