from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report process liveness without claiming dependency readiness."""

    return HealthResponse(status="ok", service="JobSift API", version="0.1.0")
