"""
ChessMate AI – Vision Pipeline Orchestrator
--------------------------------------------
Runs all 8 stages in order per alignment notes Rule 3.
Implements Rule 4 + Rule 5 session guardrails throughout.

Confidence composition (Adjustment 6):
--------------------------------------
VisionResult.confidence is a weighted composite of two signals:

  1. board_detect_conf  (weight: CONFIDENCE_WEIGHT_BOARD_DETECT, default 0.70)
     Source: Stage 1. Combines quadrilateral aspect ratio (squareness) and
     area coverage of the frame. Range 0.0–1.0.

  2. piece_coverage_conf  (weight: CONFIDENCE_WEIGHT_PIECE_COVERAGE, default 0.30)
     Source: Stage 4+6. occupied_count / PIECE_COVERAGE_EXPECTED (default 16).
     Capped at 1.0. Rewards positions with a plausible number of pieces.
     NOTE: this penalises endgames with few pieces — acceptable for MVP.

  composite = board_detect * 0.70 + piece_coverage * 0.30

All weights are in config. The detail breakdown is returned in
VisionResult.confidence_detail for debugging and future threshold tuning.

Debug artifacts (Adjustment 2):
---------------------------------
When request.debug=True, the pipeline renders and base64-encodes:
  contour_overlay  — Stage 1: detected board quad on original frame
  rectified_board  — Stage 2: warped 512×512 board
  grid_overlay     — Stage 3: 8×8 grid drawn on rectified board
  occupancy_map    — Stage 4: squares coloured by occupancy
"""
from __future__ import annotations
import base64
import collections
import logging
import time
import cv2
import numpy as np

from app.core.config import settings
from app.models.vision import VisionResult, BoardCorners, DebugArtifacts
from app.stages.stage1_board_detection      import detect_board, BoardNotFoundError
from app.stages.stage2_perspective          import correct_perspective, WARP_SIZE, SQ_SIZE
from app.stages.stage3_square_extraction    import extract_squares
from app.stages.stage4_occupancy            import detect_occupancy
from app.stages.stage5_piece_color          import detect_piece_colors
from app.stages.stage6_piece_classification import classify_pieces
from app.stages.stage6_gemini               import classify_with_gemini, classify_full_frame
from app.stages.stage7_fen_generation       import generate_fen
from app.stages.stage8_legality             import validate_fen

logger = logging.getLogger(__name__)

# ── FEN Consensus Buffer ─────────────────────────────────────────────────
# Requires CONSENSUS_REQUIRED matching board FENs in the last CONSENSUS_WINDOW
# scans before accepting a position. This filters frame-to-frame noise.
CONSENSUS_WINDOW = 5
CONSENSUS_REQUIRED = 3
_fen_history: collections.deque[str] = collections.deque(maxlen=CONSENSUS_WINDOW)


def _board_fen(full_fen: str) -> str:
    """Extract just the board part of a FEN (before the first space)."""
    return full_fen.split(" ")[0] if " " in full_fen else full_fen


def _fen_diff_squares(fen_a: str, fen_b: str) -> int:
    """Count how many squares differ between two board FENs."""
    def expand(board_fen: str) -> list[str]:
        squares = []
        for ch in board_fen.replace("/", ""):
            if ch.isdigit():
                squares.extend(["." for _ in range(int(ch))])
            else:
                squares.append(ch)
        return squares

    a = expand(_board_fen(fen_a))
    b = expand(_board_fen(fen_b))
    if len(a) != 64 or len(b) != 64:
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def _check_consensus(board_fen: str) -> bool:
    """Returns True if board_fen has appeared >= CONSENSUS_REQUIRED times recently."""
    _fen_history.append(board_fen)
    count = sum(1 for f in _fen_history if f == board_fen)
    return count >= CONSENSUS_REQUIRED


# ── Helpers ───────────────────────────────────────────────────────────────

def _decode_image(image_b64: str) -> np.ndarray:
    data  = base64.b64decode(image_b64)
    arr   = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Failed to decode image — ensure JPEG or PNG base64.")
    return frame


def _to_b64(img: np.ndarray, quality: int = 80) -> str:
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode()


def _build_debug_artifacts(
    frame:    np.ndarray,
    corners:  np.ndarray,
    warped:   np.ndarray,
    occupied: list[bool],
) -> DebugArtifacts:
    """Render all four debug images and return as DebugArtifacts."""
    arts = DebugArtifacts()

    # 1. Contour overlay — draw detected quadrilateral on original frame
    overlay = frame.copy()
    pts = corners.reshape((-1, 1, 2)).astype(np.int32)
    cv2.polylines(overlay, [pts], isClosed=True, color=(0, 200, 80), thickness=3)
    for pt in corners:
        cv2.circle(overlay, tuple(pt.astype(int)), 8, (0, 200, 80), -1)
    arts.contour_overlay = _to_b64(overlay)

    # 2. Rectified board — straight from Stage 2 output
    arts.rectified_board = _to_b64(warped)

    # 3. Grid overlay — 8×8 lines on rectified board
    grid = warped.copy()
    for i in range(1, 8):
        x = i * SQ_SIZE
        cv2.line(grid, (x, 0), (x, WARP_SIZE), (0, 200, 80), 1)
        cv2.line(grid, (0, x), (WARP_SIZE, x), (0, 200, 80), 1)
    arts.grid_overlay = _to_b64(grid)

    # 4. Occupancy map — colour squares by occupancy result
    occ_map = warped.copy()
    for idx, is_occ in enumerate(occupied):
        row, col = divmod(idx, 8)
        x0, y0   = col * SQ_SIZE, row * SQ_SIZE
        color    = (0, 180, 60) if is_occ else (60, 60, 60)
        cv2.rectangle(occ_map, (x0, y0), (x0 + SQ_SIZE, y0 + SQ_SIZE), color, 2)
    arts.occupancy_map = _to_b64(occ_map)

    return arts


def _compute_confidence(
    board_detect_conf: float,
    occupied:          list[bool],
) -> tuple[float, dict[str, float]]:
    """
    Adjustment 6: Composite confidence with documented formula.
    Returns (composite, detail_dict).
    """
    piece_count      = sum(occupied)
    piece_coverage   = min(piece_count / settings.PIECE_COVERAGE_EXPECTED, 1.0)
    w_board          = settings.CONFIDENCE_WEIGHT_BOARD_DETECT
    w_coverage       = settings.CONFIDENCE_WEIGHT_PIECE_COVERAGE
    composite        = board_detect_conf * w_board + piece_coverage * w_coverage

    detail = {
        "board_detect":    round(board_detect_conf, 4),
        "piece_coverage":  round(piece_coverage, 4),
        "composite":       round(composite, 4),
        "piece_count":     float(piece_count),
    }
    return float(np.clip(composite, 0.0, 1.0)), detail


def _dummy_occupied(fen: str) -> list[bool]:
    """Build an occupied list from a FEN string for confidence calculation."""
    board = fen.split(" ")[0] if " " in fen else fen
    occupied = []
    for ch in board.replace("/", ""):
        if ch.isdigit():
            occupied.extend([False] * int(ch))
        else:
            occupied.append(True)
    while len(occupied) < 64:
        occupied.append(False)
    return occupied[:64]


def _fallback(result: VisionResult, last_known_good_fen: str | None, t0: float) -> VisionResult:
    """Rule 5: preserve lastKnownGoodFen, do not overwrite session state."""
    result.used_fallback = True
    result.fallback_fen  = last_known_good_fen
    result.fen           = last_known_good_fen or ""
    result.legal         = bool(last_known_good_fen)
    result.latency_ms    = (time.perf_counter() - t0) * 1000
    return result


# ── Main pipeline ─────────────────────────────────────────────────────────

def _rotate_board(warped: np.ndarray, white_side: str) -> np.ndarray:
    """Rotate warped board so white always plays from the bottom."""
    if white_side == "top":
        return cv2.rotate(warped, cv2.ROTATE_180)
    elif white_side == "left":
        return cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    elif white_side == "right":
        return cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return warped  # "bottom" or default — no rotation


def run_pipeline(
    image_b64:           str,
    last_known_good_fen: str | None = None,
    previous_fen:        str | None = None,
    debug:               bool       = False,
    pinned_corners:      list[list[float]] | None = None,
    white_side:          str | None = None,
) -> VisionResult:
    """
    Execute all 8 vision stages in alignment-note order.
    Short-circuits to fallback on low confidence or board-not-found (Rule 5).
    """
    t0     = time.perf_counter()
    result = VisionResult()

    # ── Decode ─────────────────────────────────────────────────────────────
    try:
        frame = _decode_image(image_b64)
    except Exception as exc:
        result.error = f"Image decode error: {exc}"
        logger.error(result.error)
        return _fallback(result, last_known_good_fen, t0)

    use_llm = settings.USE_GEMINI and (settings.OLLAMA_URL or settings.GEMINI_API_KEY)

    if use_llm:
        # ── LLM path: send full frame, skip all CV stages ─────────────────
        result.board_found = True
        result.stage_reached = 7
        board_fen = classify_full_frame(frame)
        if board_fen:
            fen = f"{board_fen} w - - 0 1"
            logger.info("LLM FEN: %s", fen)
        else:
            result.error = "LLM classification returned no result"
            logger.warning(result.error)
            return _fallback(result, last_known_good_fen, t0)

        # ── Legality validation ────────────────────────────────────────────
        validation = validate_fen(fen)
        result.stage_reached = 8
        result.legal = validation.legal

        if not validation.legal:
            result.fen = fen
            result.error = f"Stage 8 (legality): {validation.reason}"
            result.latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Illegal FEN | fen=%r | reason=%s", fen, validation.reason)
            result.confidence = 0.95
            return _fallback(result, last_known_good_fen, t0)

        result.confidence = 0.95
        result.confidence_detail = {"classifier": 1.0}
        result.fen = fen
        result.used_fallback = False

    else:
        # ── CV heuristic path: stages 1-7 ─────────────────────────────────
        # Stage 1: Board detection
        if pinned_corners and len(pinned_corners) == 4:
            corners = np.array(pinned_corners, dtype="float32")
            detect_conf = 0.99
            result.board_found = True
            result.stage_reached = 1
            result.corners = BoardCorners(
                top_left=pinned_corners[0], top_right=pinned_corners[1],
                bottom_right=pinned_corners[2], bottom_left=pinned_corners[3],
            )
        else:
            try:
                corners, detect_conf = detect_board(frame)
                result.board_found = True
                result.stage_reached = 1
                result.corners = BoardCorners(
                    top_left=corners[0].tolist(), top_right=corners[1].tolist(),
                    bottom_right=corners[2].tolist(), bottom_left=corners[3].tolist(),
                )
            except BoardNotFoundError as exc:
                result.error = f"Stage 1 (board detection): {exc}"
                logger.warning(result.error)
                return _fallback(result, last_known_good_fen, t0)

            if detect_conf < settings.CONFIDENCE_THRESHOLD:
                result.confidence = detect_conf
                result.error = f"Low board-detect confidence ({detect_conf:.2f})"
                logger.warning(result.error)
                return _fallback(result, last_known_good_fen, t0)

        # Stage 2: Perspective correction
        warped = correct_perspective(frame, corners)
        if white_side and white_side != "bottom":
            warped = _rotate_board(warped, white_side)
        result.stage_reached = 2

        # Stages 3-7: Heuristic classification
        squares = extract_squares(warped)
        result.stage_reached = 3
        occupied = detect_occupancy(squares)
        result.stage_reached = 4
        colors = detect_piece_colors(squares, occupied)
        result.stage_reached = 5
        pieces = classify_pieces(squares, occupied, colors)
        result.stage_reached = 6
        fen = generate_fen(pieces)
        result.stage_reached = 7

        # Stage 8: Legality
        validation = validate_fen(fen)
        result.stage_reached = 8
        result.legal = validation.legal

        if not validation.legal:
            result.fen = fen
            result.error = f"Stage 8 (legality): {validation.reason}"
            result.latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Illegal FEN | fen=%r | reason=%s", fen, validation.reason)
            composite, detail = _compute_confidence(detect_conf, occupied)
            result.confidence = composite
            result.confidence_detail = detail
            return _fallback(result, last_known_good_fen, t0)

        composite, detail = _compute_confidence(detect_conf, _dummy_occupied(fen))
        result.confidence = composite
        result.confidence_detail = detail
        if composite < settings.CONFIDENCE_THRESHOLD:
            result.error = f"Composite confidence too low ({composite:.2f})"
            logger.warning(result.error)
            return _fallback(result, last_known_good_fen, t0)

        result.fen = fen
        result.used_fallback = False

    # ── Debug artifacts (heuristic path only) ────────────────────────────
    if debug and not use_llm:
        result.debug_artifacts = _build_debug_artifacts(frame, corners, warped, occupied)

    result.latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Pipeline complete | fen=%r | conf=%.2f | latency=%.1fms",
        result.fen, result.confidence, result.latency_ms,
    )
    return result
