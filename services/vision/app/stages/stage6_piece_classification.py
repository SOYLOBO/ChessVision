"""
Vision Stage 6 – Piece Classification
----------------------------------------
Deterministic silhouette heuristics for standard Staunton sets.

Classification order matters — rules are evaluated most-specific-first
to prevent the queen/king catch-all from swallowing everything.

A CNN or YOLO model MAY replace this classifier in stage 6 ONLY.
"""
from __future__ import annotations
import cv2
import numpy as np
from app.core.config import settings


def _piece_features(sq: np.ndarray) -> dict:
    """Extract shape features from a square image."""
    h, w = sq.shape[:2]
    gray = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {
            "height_ratio": 0, "aspect": 1, "solidity": 0,
            "top_mass": 0.5, "total_mass": 0, "width_ratio": 0,
            "top_width_ratio": 0,
        }

    cnt = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(cnt)
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    cnt_area = cv2.contourArea(cnt)
    solidity = cnt_area / hull_area if hull_area > 0 else 0

    top_third = bw[:h // 3, :]
    top_mass = float(np.sum(top_third > 0)) / (top_third.size + 1e-6)
    total_mass = float(np.sum(bw > 0)) / (bw.size + 1e-6)

    top_quarter = bw[:h // 4, :]
    top_cols = np.any(top_quarter > 0, axis=0)
    top_width = float(np.sum(top_cols)) / (w + 1e-6)

    return {
        "height_ratio": ch / h,
        "aspect": ch / (cw + 1e-6),
        "solidity": solidity,
        "top_mass": top_mass,
        "total_mass": total_mass,
        "width_ratio": cw / (w + 1e-6),
        "top_width_ratio": top_width,
    }


def _classify_features(f: dict) -> str:
    """
    Rule-based classifier. Order: pawn → rook → knight → bishop → king → queen.
    Pawn is the default fallback — it's the most common piece and safest FEN default.
    """
    hr = f["height_ratio"]
    asp = f["aspect"]
    sol = f["solidity"]
    tm = f["top_mass"]
    total = f["total_mass"]
    tw = f["top_width_ratio"]

    # Pawn: short, compact, round
    if hr < settings.CLF_PAWN_MAX_HEIGHT_RATIO and sol > settings.CLF_PAWN_MIN_SOLIDITY:
        return "p"

    # Pawn: slightly taller but still compact with low total mass
    if hr < 0.60 and sol > 0.65 and total < 0.30:
        return "p"

    # Rook: tall, flat top (low top mass), blocky (high solidity), wide top
    if (hr > settings.CLF_ROOK_MIN_HEIGHT_RATIO and
            tm < settings.CLF_ROOK_MAX_TOP_MASS and
            sol > settings.CLF_ROOK_MIN_SOLIDITY and
            tw > 0.30):
        return "r"

    # Knight: asymmetric horse head → low solidity (indentation)
    if (settings.CLF_KNIGHT_MIN_HEIGHT_RATIO < hr < settings.CLF_KNIGHT_MAX_HEIGHT_RATIO and
            sol < settings.CLF_KNIGHT_MAX_SOLIDITY):
        return "n"

    # Bishop: tall, narrow, pointed top
    if (hr > settings.CLF_BISHOP_MIN_HEIGHT_RATIO and
            asp > settings.CLF_BISHOP_MIN_ASPECT and
            tw < 0.35 and
            tm < settings.CLF_BISHOP_MAX_TOP_MASS):
        return "b"

    # King: tallest, narrow cross on top → tall aspect, narrow top
    if hr > settings.CLF_KING_MIN_HEIGHT_RATIO and asp > 1.3 and tw < 0.50:
        return "k"

    # Queen: tall with wide ornate crown
    if (hr > settings.CLF_QUEEN_MIN_HEIGHT_RATIO and
            tm > settings.CLF_QUEEN_MIN_TOP_MASS and
            tw > 0.40):
        return "q"

    # Medium-height unclassified → pawn
    if hr < 0.65:
        return "p"

    # Tall, solid, unclassified → rook
    if sol > 0.55:
        return "r"

    return "p"


def classify_pieces(
    squares: list[np.ndarray],
    occupied: list[bool],
    colors: list[str | None],
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
