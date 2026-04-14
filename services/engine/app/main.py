"""
ChessMate AI – Engine Service
FastAPI application entrypoint.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.stockfish import StockfishEngine
from app.routers import analysis, health


# ---------------------------------------------------------------------------
# Lifespan: boot / teardown the persistent Stockfish process
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = StockfishEngine()
    engine.start()
    app.state.engine = engine
    yield
    engine.stop()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="ChessMate AI – Engine Service",
        description="Stockfish UCI wrapper with template-based coaching output.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(analysis.router, prefix="/analyze-position", tags=["analysis"])

    return app


app = create_app()
