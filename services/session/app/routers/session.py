"""
ChessMate AI – Session Service Routers

POST /sessions              Create session
GET  /sessions/{id}         Get session state
POST /sessions/{id}/update  Apply vision result to session
POST /sessions/{id}/end     End session
GET  /health
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.models.session import (
    CreateSessionRequest, UpdateSessionRequest,
    SessionResponse
)
from app.core.store import create_session, get_session, update_session, end_session

router = APIRouter(prefix="/sessions")
health_router = APIRouter()


def _to_response(state) -> SessionResponse:
    return SessionResponse(
        session_id       = state.session_id,
        currentFen       = state.currentFen,
        previousFen      = state.previousFen,
        lastKnownGoodFen = state.lastKnownGoodFen,
        mode             = state.mode,
        skillLevel       = state.skillLevel,
        moveHistory      = state.moveHistory,
        scanConfidence   = state.scanConfidence,
        active           = state.active,
        frame_count      = state.frame_count,
        fallback_count   = state.fallback_count,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create(body: CreateSessionRequest) -> SessionResponse:
    state = create_session(
        mode         = body.mode,
        skill_level  = body.skillLevel,
        starting_fen = body.starting_fen,
    )
    return _to_response(state)


@router.get("/{session_id}", response_model=SessionResponse)
async def get(session_id: str) -> SessionResponse:
    state = get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return _to_response(state)


@router.post("/{session_id}/update", response_model=SessionResponse)
async def update(session_id: str, body: UpdateSessionRequest) -> SessionResponse:
    state = update_session(
        session_id    = session_id,
        new_fen       = body.new_fen,
        legal         = body.legal,
        confidence    = body.confidence,
        used_fallback = body.used_fallback,
    )
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return _to_response(state)


@router.post("/{session_id}/end")
async def end(session_id: str) -> dict:
    ok = end_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return {"ended": True, "session_id": session_id}


@health_router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "session"}
