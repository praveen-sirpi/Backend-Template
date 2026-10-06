"""Wire up every module's router. Add new feature modules to `api_router`."""

from fastapi import APIRouter

from src.modules import auth, health, users

# Infrastructure endpoints, served without the API prefix: /, /health, /health/ready
root_router = APIRouter()
root_router.include_router(health.router)

# Versioned API, mounted at settings.api_prefix (default /api/v1)
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
