"""
Vision Stage 7 – FEN Generation
----------------------------------
Assembles the 64-square piece list into a FEN position string.

MVP DEFAULTS — TEMPORARY (Adjustment 3)
----------------------------------------
The fields beyond the board diagram (side-to-move, castling rights,
en passant, halfmove clock, fullmove number) are currently hardcoded
to conservative defaults:

    side-to-move : 'w'   — always white; WRONG after black moves
    castling     : '-'   — no castling rights assumed; loses castling info
    en passant   : '-'   — no en passant; misses en-passant opportunities
    halfmove     : 0
    fullmove     : 1

These defaults are acceptable ONLY for the early prototype flow where
the session service has no move history to infer from.

Required upgrade path (not part of MVP):
  - Session service tracks moveHistory and side-to-move
  - Vision service accepts `side_to_move` and `last_move` as optional
    request fields
  - Stage 7 uses those to construct a correct full FEN
  - Castling rights require additional state (have king/rooks moved?)
    and must be explicitly tracked in session, not inferred from vision

Until that upgrade is implemented, callers should treat the FEN's
metadata fields as approximate and rely on the board diagram only.
"""
from __future__ import annotations


def generate_fen(pieces: list[str | None]) -> str:
    """
    Stage 7: Convert 64-element piece list to FEN string.

    Index 0 = a8 (top-left), index 63 = h1 (bottom-right).
    Returns full FEN with MVP placeholder metadata (see module docstring).
    """
    ranks: list[str] = []

    for rank_idx in range(8):
        empty  = 0
        rank_s = ""
        for file_idx in range(8):
            piece = pieces[rank_idx * 8 + file_idx]
            if piece is None:
                empty += 1
            else:
                if empty:
                    rank_s += str(empty)
                    empty = 0
                rank_s += piece
        if empty:
            rank_s += str(empty)
        ranks.append(rank_s)

    board_fen = "/".join(ranks)
    # TODO: replace placeholder metadata when session-aware FEN inference is implemented
    return f"{board_fen} w - - 0 1"
