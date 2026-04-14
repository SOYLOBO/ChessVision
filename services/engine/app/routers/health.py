"""
Engine Service – Health router.

GET /health
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    engine: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    engine = request.app.state.engine
    engine_status = "ok" if engine and engine._proc and engine._proc.poll() is None else "down"
    return HealthResponse(status="ok", engine=engine_status)
