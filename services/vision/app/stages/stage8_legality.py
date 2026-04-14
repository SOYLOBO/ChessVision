"""
Vision Stage 8 – Legality Validation
--------------------------------------
Validates the generated FEN with python-chess before passing to engine.
Per alignment notes Rule 5: if FEN is illegal, return legal=False,
do not analyze, log failure.
"""
from __future__ import annotations
import logging
import chess

logger = logging.getLogger(__name__)


class FENValidationResult:
    __slots__ = ("legal", "reason", "board")

    def __init__(self, legal: bool, reason: str = "", board: chess.Board | None = None):
        self.legal  = legal
        self.reason = reason
        self.board  = board


def validate_fen(fen: str) -> FENValidationResult:
    """
    Stage 8: Validate FEN string with python-chess.

    Returns FENValidationResult with:
      .legal  — True if FEN is structurally valid and board is legal
      .reason — human-readable failure reason (empty on success)
      .board  — chess.Board instance (only set on success)

    Per alignment notes Rule 5:
      - Do not proceed to engine on illegal FEN
      - Log the FEN and failure reason for debugging
      - Surface the error — do not swallow it silently
    """
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        reason = f"Invalid FEN structure: {exc}"
        logger.warning("FEN validation failed | fen=%r | reason=%s", fen, reason)
        return FENValidationResult(legal=False, reason=reason)

    # Additional sanity checks python-chess accepts but are unreachable in real games
    issues: list[str] = []

    white_kings = bin(board.pieces(chess.KING, chess.WHITE).mask).count("1")
    black_kings = bin(board.pieces(chess.KING, chess.BLACK).mask).count("1")
    if white_kings != 1:
        issues.append(f"White has {white_kings} kings (expected 1)")
    if black_kings != 1:
        issues.append(f"Black has {black_kings} kings (expected 1)")

    # Pawns on rank 1 or rank 8 are illegal
    back_ranks = chess.BB_RANK_1 | chess.BB_RANK_8
    if board.pawns & back_ranks:
        issues.append("Pawn detected on back rank")

    if issues:
        reason = "; ".join(issues)
        logger.warning("FEN legal check failed | fen=%r | reason=%s", fen, reason)
        return FENValidationResult(legal=False, reason=reason)

    return FENValidationResult(legal=True, board=board)
