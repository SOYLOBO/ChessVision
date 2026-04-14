"""
ChessMate AI – Vision Service
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers.vision import router, health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ChessMate AI – Vision Service",
        description="8-stage deterministic CV pipeline: board detection through FEN generation.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, tags=["health"])
    app.include_router(router, tags=["vision"])
    return app


app = create_app()
