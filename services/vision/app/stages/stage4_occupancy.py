"""
Vision Stage 4 – Occupancy Detection
--------------------------------------
Determines per square whether a piece is present.
Purely deterministic — pixel variance + edge density.
All thresholds are in config (Adjustment 5).
"""
from __future__ import annotations
import cv2
import numpy as np
from app.core.config import settings


def detect_occupancy(squares: list[np.ndarray]) -> list[bool]:
    """
    Stage 4: Return 64-element list — True if square is occupied.
    Combines pixel variance and edge density; either signal triggers occupied=True.
    """
    occupied: list[bool] = []
    for sq in squares:
        gray  = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY)
        var   = float(np.var(gray))
        edges = cv2.Canny(gray, 40, 120)
        edge_density = float(np.sum(edges > 0)) / edges.size
        is_occupied = (
            var          > settings.OCCUPANCY_VARIANCE_THRESHOLD or
            edge_density > settings.OCCUPANCY_EDGE_DENSITY_THRESHOLD
        )
        occupied.append(bool(is_occupied))
    return occupied
