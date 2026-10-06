from typing import Literal

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
