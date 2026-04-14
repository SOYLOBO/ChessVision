"""
Vision Stage 2 – Perspective Correction
-----------------------------------------
Warps the detected board quadrilateral to a clean top-down square image.
Output size is configurable; defaults to 512×512 (64px per square).
"""
from __future__ import annotations
import cv2
import numpy as np

WARP_SIZE = 512   # output image side length in pixels
SQ_SIZE   = WARP_SIZE // 8  # 64px per square


def correct_perspective(frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """
    Stage 2: Warp board corners to a square top-down view.

    Parameters
    ----------
    frame   : BGR image
    corners : (4, 2) float32 in [TL, TR, BR, BL] order

    Returns
    -------
    warped : (WARP_SIZE, WARP_SIZE, 3) BGR image
    """
    dst = np.array([
        [0,         0        ],
        [WARP_SIZE, 0        ],
        [WARP_SIZE, WARP_SIZE],
        [0,         WARP_SIZE],
    ], dtype="float32")

    M      = cv2.getPerspectiveTransform(corners, dst)
    warped = cv2.warpPerspective(frame, M, (WARP_SIZE, WARP_SIZE))
    return warped
