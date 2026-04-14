"""
Vision Stage 3 – Square Extraction
-------------------------------------
Segments the warped 512×512 board image into 64 individual square crops.
Index order: a8=0, b8=1 … h8=7, a7=8 … h1=63  (rank 8 to 1, file a to h).
This matches FEN rank ordering (rank 8 first).
"""
from __future__ import annotations
import numpy as np
from app.stages.stage2_perspective import SQ_SIZE

# Small inset to avoid border bleed between squares
INSET = 4


def extract_squares(warped: np.ndarray) -> list[np.ndarray]:
    """
    Stage 3: Return list of 64 square image crops.

    Parameters
    ----------
    warped : (512, 512, 3) BGR board image from stage 2

    Returns
    -------
    squares : list of 64 BGR crops, each (SQ_SIZE-2*INSET, SQ_SIZE-2*INSET, 3)
    """
    squares: list[np.ndarray] = []
    for row in range(8):      # rank 8 down to rank 1
        for col in range(8):  # file a to h
            y0 = row * SQ_SIZE + INSET
            y1 = y0  + SQ_SIZE - 2 * INSET
            x0 = col * SQ_SIZE + INSET
            x1 = x0  + SQ_SIZE - 2 * INSET
            squares.append(warped[y0:y1, x0:x1])
    return squares
