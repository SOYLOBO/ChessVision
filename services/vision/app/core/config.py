"""
ChessMate AI – Vision Service Configuration
All tunable thresholds are here. Override via environment variables or .env.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── Confidence (Adjustment 6) ─────────────────────────────────────────
    # Below this, preserve lastKnownGoodFen and do not call engine (Rule 5)
    CONFIDENCE_THRESHOLD: float = 0.65
    # Weights for composite confidence formula
    CONFIDENCE_WEIGHT_BOARD_DETECT:   float = 0.70
    CONFIDENCE_WEIGHT_PIECE_COVERAGE: float = 0.30
    # Expected piece count mid-game for coverage normalisation
    PIECE_COVERAGE_EXPECTED: int = 16

    # ── Stage 1: Board detection ──────────────────────────────────────────
    MIN_BOARD_AREA_RATIO: float = 0.10   # min contour area as fraction of frame
    CANNY_LOW:            int   = 30
    CANNY_HIGH:           int   = 120
    BOARD_DETECT_TOP_N:   int   = 10     # max contours to evaluate

    # ── Stage 4: Occupancy detection ─────────────────────────────────────
    OCCUPANCY_VARIANCE_THRESHOLD: float = 180.0  # pixel variance — below = empty
    OCCUPANCY_EDGE_DENSITY_THRESHOLD: float = 0.06  # edge pixel fraction — above = occupied

    # ── Stage 5: Piece color classification ──────────────────────────────
    # Center crop margin (fraction) used to sample piece brightness
    COLOR_CENTER_MARGIN: float = 0.30
    # Brightness thresholds for light/dark square contexts
    COLOR_LIGHT_SQ_THRESHOLD: int = 140  # on a light square: above = white piece
    COLOR_DARK_SQ_THRESHOLD:  int = 110  # on a dark square:  above = white piece

    # ── Stage 6: Piece classification heuristics ─────────────────────────
    # NOTE (Adjustment 4): These are placeholder heuristic thresholds.
    # Stage 6 is the only stage where an ML model (CNN/YOLO) may replace
    # this classifier in a future iteration. Do not move ML into any other stage.
    CLF_PAWN_MAX_HEIGHT_RATIO:    float = 0.55
    CLF_PAWN_MIN_SOLIDITY:        float = 0.65
    CLF_ROOK_MIN_HEIGHT_RATIO:    float = 0.65
    CLF_ROOK_MAX_TOP_MASS:        float = 0.12
    CLF_ROOK_MIN_SOLIDITY:        float = 0.60
    CLF_KNIGHT_MIN_HEIGHT_RATIO:  float = 0.55
    CLF_KNIGHT_MAX_HEIGHT_RATIO:  float = 0.80
    CLF_KNIGHT_MAX_SOLIDITY:      float = 0.60
    CLF_BISHOP_MIN_HEIGHT_RATIO:  float = 0.70
    CLF_BISHOP_MIN_ASPECT:        float = 1.80
    CLF_BISHOP_MAX_TOP_MASS:      float = 0.14
    CLF_QUEEN_MIN_HEIGHT_RATIO:   float = 0.80
    CLF_QUEEN_MIN_TOP_MASS:       float = 0.13
    CLF_KING_MIN_HEIGHT_RATIO:    float = 0.80

    # ── Debug output ──────────────────────────────────────────────────────
    DEBUG_SAVE_FRAMES:  bool = False
    DEBUG_OUTPUT_DIR:   str  = "/tmp/chessmate_debug"

    # ── Transport (Rule 7) ────────────────────────────────────────────────
    # meta_glasses | phone | webcam
    INPUT_MODE: str = "webcam"

    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
