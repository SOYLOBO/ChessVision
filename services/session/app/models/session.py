"""
ChessMate AI – Session State Models
All 7 fields required by alignment notes Rule 4.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CoachMode(str, Enum):
    CASUAL        = "casual"
    STUDY         = "study"
    PUZZLE        = "puzzle"
    BLUNDER_CHECK = "blunder_check"
    OPENING       = "opening"


class SessionState(BaseModel):
    """
    Rule 4: All 7 required session fields.
    lastKnownGoodFen is the critical failure fallback anchor.

    moveHistory semantics (Adjustment 7):
    ---------------------------------------
    Currently stores confirmed FEN snapshots on each position change,
    NOT UCI move strings (e.g. 'e2e4').

    This is a temporary MVP behaviour. The field is named moveHistory
    to match the alignment notes spec, but its content will change when
    move detection is implemented (diff between previousFen and currentFen
    via python-chess move generation).

    Future: store UCI move strings ['e2e4', 'd7d5', ...] once the session
    service can compute the legal move between two consecutive FENs.
    Until then, treat moveHistory entries as FEN position anchors.
    """
    session_id:       str
    currentFen:       str       = ""
    previousFen:      str       = ""
    lastKnownGoodFen: str       = ""   # ← Rule 4: only updated on confirmed good scan
    mode:             CoachMode = CoachMode.CASUAL
    skillLevel:       int       = Field(20, ge=0, le=20)
    moveHistory:      list[str] = Field(default_factory=list)  # see docstring above
    scanConfidence:   float     = 0.0

    active:           bool = True
    frame_count:      int  = 0
    fallback_count:   int  = 0


class CreateSessionRequest(BaseModel):
    mode:         CoachMode    = CoachMode.CASUAL
    skillLevel:   int          = Field(20, ge=0, le=20)
    starting_fen: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    session_id:    str
    new_fen:       str
    legal:         bool
    confidence:    float
    used_fallback: bool           = False
    latency_ms:    Optional[float] = None


class SessionResponse(BaseModel):
    session_id:           str
    currentFen:           str
    previousFen:          str
    lastKnownGoodFen:     str
    mode:                 CoachMode
    skillLevel:           int
    moveHistory:          list[str]
    moveHistory_note:     str = (
        "MVP: stores FEN snapshots, not UCI move strings. "
        "Will change to UCI moves once move detection is implemented."
    )
    scanConfidence:       float
    active:               bool
    frame_count:          int
    fallback_count:       int
