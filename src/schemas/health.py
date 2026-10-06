from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "error", "disabled"]


class AppInfo(BaseModel):
    name: str
    version: str
    environment: str
    docs: str | None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckStatus]
