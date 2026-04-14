"""
Vision Stage 5 – Piece Color Detection
-----------------------------------------
Per occupied square: is the piece light or dark?
Purely deterministic brightness comparison.
All thresholds are in config (Adjustment 5).
"""
from __future__ import annotations
import cv2
import numpy as np
from app.core.config import settings


def _is_light_square(row: int, col: int) -> bool:
    return (row + col) % 2 == 0


def detect_piece_colors(
    squares:  list[np.ndarray],
    occupied: list[bool],
) -> list[str | None]:
    """
    Stage 5: Return 64-element list — None (empty), 'white', or 'black'.

    Samples the center crop (margin set in config) and compares brightness
    against context-aware thresholds for light vs dark squares.
    """
    margin = settings.COLOR_CENTER_MARGIN
    colors: list[str | None] = []

    for idx, (sq, is_occ) in enumerate(zip(squares, occupied)):
        if not is_occ:
            colors.append(None)
            continue

        row, col = divmod(idx, 8)
        gray     = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY)
        h, w     = gray.shape
        my, mx   = int(h * margin), int(w * margin)
        center   = gray[my:h - my, mx:w - mx]
        mean_val = float(np.mean(center))

        if _is_light_square(row, col):
            piece_color = "white" if mean_val > settings.COLOR_LIGHT_SQ_THRESHOLD else "black"
        else:
            piece_color = "white" if mean_val > settings.COLOR_DARK_SQ_THRESHOLD  else "black"

        colors.append(piece_color)

    return colors
