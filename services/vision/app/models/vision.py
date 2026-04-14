"""
ChessMate AI – Vision Service Models
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class InputMode(str, Enum):
    META_GLASSES = "meta_glasses"
    PHONE        = "phone"
    WEBCAM       = "webcam"


# ── Request ───────────────────────────────────────────────────────────────

class AnalyzeFrameRequest(BaseModel):
    image_b64:           str       = Field(..., description="Base64-encoded JPEG or PNG frame.")
    input_mode:          InputMode = Field(InputMode.WEBCAM, description="Frame source (Rule 7).")
    previous_fen:        Optional[str] = Field(None, description="previousFen from session — used for diff validation.")
    last_known_good_fen: Optional[str] = Field(None, description="lastKnownGoodFen — returned unchanged on low-confidence frames.")
    debug:               bool      = Field(False, description="When True, include base64 debug images in response.")
    pinned_corners:      Optional[list[list[float]]] = Field(None, description="4 corners [[x,y],...] in TL,TR,BR,BL order — skips board detection.")
    white_side:          Optional[str] = Field(None, description="Which edge white plays from: bottom, top, left, right.")


# ── Sub-models ────────────────────────────────────────────────────────────

class BoardCorners(BaseModel):
    top_left:     list[float]
    top_right:    list[float]
    bottom_right: list[float]
    bottom_left:  list[float]


class SquareOccupancy(BaseModel):
    """64-element grid. Index 0 = a8."""
    occupied: list[bool] = Field(..., min_length=64, max_length=64)


class DebugArtifacts(BaseModel):
    """
    Adjustment 2: Debug image payloads for pipeline introspection.
    All fields are base64-encoded JPEG strings. Only populated when request.debug=True.

    contour_overlay  — Stage 1: detected board quadrilateral drawn on original frame
    rectified_board  — Stage 2: perspective-corrected 512×512 board
    grid_overlay     — Stage 3: 8×8 grid lines drawn on rectified board
    occupancy_map    — Stage 4: squares coloured by occupancy (green=occupied, grey=empty)
    stage_snapshots  — Optional per-stage intermediate images (keyed by stage name)
    """
    contour_overlay:  Optional[str] = None   # base64 JPEG
    rectified_board:  Optional[str] = None   # base64 JPEG
    grid_overlay:     Optional[str] = None   # base64 JPEG
    occupancy_map:    Optional[str] = None   # base64 JPEG
    stage_snapshots:  dict[str, str] = Field(default_factory=dict)


# ── Response ──────────────────────────────────────────────────────────────

class VisionResult(BaseModel):
    # Core outputs
    fen:            str   = ""
    legal:          bool  = False
    confidence:     float = 0.0

    # Confidence breakdown (Adjustment 6)
    confidence_detail: dict[str, float] = Field(
        default_factory=dict,
        description="Per-stage confidence components: board_detect, piece_coverage, composite."
    )

    # Session guardrail fields (Rule 4 + 5)
    used_fallback:  bool          = False
    fallback_fen:   Optional[str] = None

    # Debug / pipeline introspection
    board_found:    bool                   = False
    corners:        Optional[BoardCorners] = None
    stage_reached:  int                    = 0
    error:          Optional[str]          = None
    debug_artifacts: Optional[DebugArtifacts] = None   # Adjustment 2

    # Latency
    latency_ms:     Optional[float] = None
