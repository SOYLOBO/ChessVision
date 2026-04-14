"""
ChessMate AI – Session Store
In-memory session registry with full Rule 4 + Rule 5 state management.

Rule 4:  Track currentFen, previousFen, lastKnownGoodFen, mode,
         skillLevel, moveHistory, scanConfidence.
Rule 5:  On low confidence or illegal FEN — preserve lastKnownGoodFen,
         do not overwrite session state with a bad read.
"""
from __future__ import annotations
import logging
import uuid
from app.models.session import SessionState, CoachMode
from app.core.config import settings

logger = logging.getLogger(__name__)

# Single in-process store — replace with Redis for multi-instance deployment
_sessions: dict[str, SessionState] = {}


def create_session(
    mode:         CoachMode = CoachMode.CASUAL,
    skill_level:  int       = 20,
    starting_fen: str | None = None,
) -> SessionState:
    sid   = str(uuid.uuid4())
    state = SessionState(
        session_id       = sid,
        mode             = mode,
        skillLevel       = skill_level,
        currentFen       = starting_fen or "",
        lastKnownGoodFen = starting_fen or "",
    )
    _sessions[sid] = state
    logger.info("Session created | id=%s | mode=%s | skill=%d", sid, mode, skill_level)
    return state


def get_session(session_id: str) -> SessionState | None:
    return _sessions.get(session_id)


def update_session(
    session_id:    str,
    new_fen:       str,
    legal:         bool,
    confidence:    float,
    used_fallback: bool = False,
) -> SessionState | None:
    """
    Apply a vision pipeline result to session state.

    Rule 5 logic:
    - used_fallback=True or confidence < threshold → do NOT touch currentFen or lastKnownGoodFen
    - illegal FEN (legal=False)                   → do NOT update any FEN fields
    - good result                                 → rotate previousFen, set currentFen, update lastKnownGoodFen
    """
    state = _sessions.get(session_id)
    if state is None:
        return None

    state.frame_count    += 1
    state.scanConfidence  = confidence

    low_confidence = confidence < settings.CONFIDENCE_THRESHOLD

    if used_fallback or low_confidence or not legal:
        # Rule 5: preserve lastKnownGoodFen — do not overwrite with bad state
        state.fallback_count += 1
        logger.warning(
            "Session state preserved (no update) | id=%s | legal=%s | conf=%.2f | fallback=%s",
            session_id, legal, confidence, used_fallback
        )
        return state

    # Good scan — update all three FEN fields
    state.previousFen      = state.currentFen
    state.currentFen       = new_fen
    state.lastKnownGoodFen = new_fen          # ← only updated on confirmed good scan

    # Append move to history if position changed
    if state.previousFen and state.previousFen != new_fen:
        state.moveHistory.append(new_fen)     # stores FEN; swap for UCI move when move detection added

    logger.info(
        "Session updated | id=%s | conf=%.2f | moves=%d",
        session_id, confidence, len(state.moveHistory)
    )
    return state


def end_session(session_id: str) -> bool:
    state = _sessions.get(session_id)
    if state:
        state.active = False
        logger.info("Session ended | id=%s | frames=%d | fallbacks=%d",
                    session_id, state.frame_count, state.fallback_count)
    return state is not None


def list_sessions() -> list[str]:
    return list(_sessions.keys())
