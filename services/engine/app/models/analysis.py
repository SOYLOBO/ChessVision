"""
Engine Service – Pydantic models.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import chess


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CoachMode(str, Enum):
    CASUAL = "casual"
    STUDY = "study"
    PUZZLE = "puzzle"
    BLUNDER_CHECK = "blunder_check"
    OPENING = "opening"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    fen: str = Field(..., description="FEN string representing the board position.")
    mode: CoachMode = Field(CoachMode.CASUAL, description="Coaching mode.")
    skillLevel: int = Field(
        20,
        ge=0,
        le=20,
        description="Stockfish skill level (0 = weakest, 20 = strongest).",
    )
    depth: Optional[int] = Field(None, ge=1, le=30, description="Search depth override.")
    multiPv: Optional[int] = Field(None, ge=1, le=5, description="Number of top moves to return.")

    @field_validator("fen")
    @classmethod
    def validate_fen(cls, v: str) -> str:
        try:
            chess.Board(v)
        except ValueError as exc:
            raise ValueError(f"Invalid FEN: {exc}") from exc
        return v


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class MoveInfo(BaseModel):
    move: str = Field(..., description="UCI move string (e.g. 'e2e4').")
    score: float = Field(..., description="Score in pawns (centipawns / 100). 999 = forced mate.")
    pv: list[str] = Field(default_factory=list, description="Principal variation moves.")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class AnalysisResult(BaseModel):
    bestMove: str
    evaluation: float = Field(..., description="Score in pawns from side-to-move perspective.")
    topMoves: list[MoveInfo]
    principalVariation: list[str]
    coachText: str = ""
    speakText: str = ""
