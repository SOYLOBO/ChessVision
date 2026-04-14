"""
Vision Stage 1 – Board Detection
----------------------------------
Finds the chess board in a frame using contour analysis.
Returns the four corner points in [TL, TR, BR, BL] order.
Pure deterministic OpenCV — no ML.
"""
from __future__ import annotations
import cv2
import numpy as np
from app.core.config import settings


class BoardNotFoundError(RuntimeError):
    pass


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Sort 4 points into [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype="float32")
    s    = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]     # top-left     (min sum)
    rect[2] = pts[np.argmax(s)]     # bottom-right (max sum)
    rect[1] = pts[np.argmin(diff)]  # top-right    (min diff)
    rect[3] = pts[np.argmax(diff)]  # bottom-left  (max diff)
    return rect


def detect_board(frame: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Stage 1: Locate the chessboard quadrilateral in the frame.

    Returns
    -------
    corners : (4, 2) float32  [TL, TR, BR, BL]
    confidence : float 0–1

    Raises
    ------
    BoardNotFoundError if no qualifying quadrilateral is found.
    """
    h, w = frame.shape[:2]
    min_area = h * w * settings.MIN_BOARD_AREA_RATIO

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # CLAHE — improves detection under uneven lighting (glasses / phone use cases)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray  = clahe.apply(gray)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 30, 120)
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    best_corners: np.ndarray | None = None
    best_score   = 0.0

    for cnt in contours[:10]:
        area = cv2.contourArea(cnt)
        if area < min_area:
            break

        peri  = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4:
            continue

        corners = _order_corners(approx.reshape(4, 2).astype("float32"))

        side_a  = float(np.linalg.norm(corners[1] - corners[0]))
        side_b  = float(np.linalg.norm(corners[2] - corners[1]))
        if side_b == 0:
            continue

        # Score: reward square-ness (aspect) and frame coverage (area)
        aspect     = min(side_a, side_b) / max(side_a, side_b)
        area_ratio = area / (h * w)
        score      = aspect * 0.6 + min(area_ratio * 3, 0.4)

        if score > best_score:
            best_score   = score
            best_corners = corners

    if best_corners is None:
        raise BoardNotFoundError("No board-like quadrilateral found in frame.")

    confidence = float(np.clip(best_score, 0.0, 1.0))
    return best_corners, confidence
