"""
Vision Stage 6 – Piece Classification
----------------------------------------
BASELINE IMPLEMENTATION — PLACEHOLDER STATUS (Adjustment 4)
------------------------------------------------------------
This classifier uses deterministic silhouette heuristics tuned for standard
Staunton sets under normal lighting. It is intentionally simple.

Replacement rule (from alignment notes, Rule 3):
  A CNN or YOLO model MAY replace this classifier in stage 6 ONLY.
  No ML model may be introduced in any other stage.
  Do not touch stages 1–5 or 7–8 when upgrading classification.

All thresholds are externalised to config (Adjustment 5) and can be
tuned without code changes.
"""
from __future__ import annotations
import cv2
import numpy as np
from app.core.config import settings


def _piece_features(sq: np.ndarray) -> dict:
    """Extract shape features from a square image."""
    h, w = sq.shape[:2]
    gray  = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"height_ratio": 0, "aspect": 1, "solidity": 0, "top_mass": 0.5, "total_mass": 0}

    cnt       = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(cnt)
    hull      = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    cnt_area  = cv2.contourArea(cnt)
    solidity  = cnt_area / hull_area if hull_area > 0 else 0

    top_half  = bw[:h // 2, :]
    top_mass  = float(np.sum(top_half > 0)) / (top_half.size + 1e-6)
    total_mass = float(np.sum(bw > 0)) / (bw.size + 1e-6)

    return {
        "height_ratio": ch / h,
        "aspect":       ch / (cw + 1e-6),
        "solidity":     solidity,
        "top_mass":     top_mass,
        "total_mass":   total_mass,
    }


def _classify_features(f: dict) -> str:
    """
    Rule-based classifier using config-driven thresholds.
    Returns lowercase piece type letter: k q r b n p
    """
    cfg = settings
    hr  = f["height_ratio"]
    asp = f["aspect"]
    sol = f["solidity"]
    tm  = f["top_mass"]

    if hr < cfg.CLF_PAWN_MAX_HEIGHT_RATIO and sol > cfg.CLF_PAWN_MIN_SOLIDITY:
        return "p"

    if (hr > cfg.CLF_ROOK_MIN_HEIGHT_RATIO and
            tm < cfg.CLF_ROOK_MAX_TOP_MASS and
            sol > cfg.CLF_ROOK_MIN_SOLIDITY):
        return "r"

    if (cfg.CLF_KNIGHT_MIN_HEIGHT_RATIO < hr < cfg.CLF_KNIGHT_MAX_HEIGHT_RATIO and
            sol < cfg.CLF_KNIGHT_MAX_SOLIDITY):
        return "n"

    if (hr > cfg.CLF_BISHOP_MIN_HEIGHT_RATIO and
            asp > cfg.CLF_BISHOP_MIN_ASPECT and
            tm < cfg.CLF_BISHOP_MAX_TOP_MASS):
        return "b"

    if hr > cfg.CLF_QUEEN_MIN_HEIGHT_RATIO and tm > cfg.CLF_QUEEN_MIN_TOP_MASS:
        return "q"

    if hr > cfg.CLF_KING_MIN_HEIGHT_RATIO:
        return "k"

    return "p"   # fallback — pawn is safest FEN default


def classify_pieces(
    squares:  list[np.ndarray],
    occupied: list[bool],
    colors:   list[str | None],
) -> list[str | None]:
    """
    Stage 6: Return 64-element list of FEN piece codes or None.
    Uppercase = white (K Q R B N P), lowercase = black (k q r b n p).
    """
    pieces: list[str | None] = []
    for sq, is_occ, color in zip(squares, occupied, colors):
        if not is_occ or color is None:
            pieces.append(None)
            continue
        piece_type = _classify_features(_piece_features(sq))
        pieces.append(piece_type.upper() if color == "white" else piece_type.lower())
    return pieces
