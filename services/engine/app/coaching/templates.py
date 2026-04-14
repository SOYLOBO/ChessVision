"""
Engine Service – Template-based coaching output.

Produces `coachText` (UI display) and `speakText` (TTS-optimized) from
analysis results and context. No LLM — pure rule-based templates.
"""

from __future__ import annotations
import chess
from app.models.analysis import AnalysisResult, CoachMode


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def _score_label(score: float) -> str:
    if score >= 999:
        return "forced mate"
    if score <= -999:
        return "being mated"
    abs_score = abs(score)
    if abs_score < 0.3:
        return "roughly equal"
    side = "white" if score > 0 else "black"
    if abs_score < 1.0:
        return f"slight edge for {side}"
    if abs_score < 2.5:
        return f"clear advantage for {side}"
    if abs_score < 5.0:
        return f"large advantage for {side}"
    return f"winning for {side}"


def _format_score(score: float) -> str:
    if score >= 999:
        return "+M"
    if score <= -999:
        return "-M"
    sign = "+" if score > 0 else ""
    return f"{sign}{score:.1f}"


def _san_from_uci(fen: str, uci_move: str) -> str:
    """Convert UCI move to SAN for human-readable output."""
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci_move)
        return board.san(move)
    except Exception:
        return uci_move


# ---------------------------------------------------------------------------
# Mode-specific template builders
# ---------------------------------------------------------------------------

def _casual_coach(result: AnalysisResult, san: str, score_label: str) -> tuple[str, str]:
    coach = (
        f"Best move: {san}. "
        f"Position is {score_label} ({_format_score(result.evaluation)} pawns)."
    )
    speak = f"Try {san}. The position is {score_label}."
    return coach, speak


def _study_coach(result: AnalysisResult, san: str, score_label: str, fen: str) -> tuple[str, str]:
    # Show top 3 alternatives if available
    alts: list[str] = []
    for mi in result.topMoves[1:3]:
        alt_san = _san_from_uci(fen, mi.move)
        alts.append(f"{alt_san} ({_format_score(mi.score)})")

    alt_text = ""
    if alts:
        alt_text = f" Alternatives: {', '.join(alts)}."

    coach = (
        f"Best: {san} ({_format_score(result.evaluation)}). "
        f"Position is {score_label}.{alt_text}"
    )
    speak = f"The best move is {san}. {score_label.capitalize()}."
    return coach, speak


def _puzzle_coach(result: AnalysisResult, san: str) -> tuple[str, str]:
    coach = f"Find the best move. Hint: think about {san[0]}."  # first character only as hint
    speak = "Look for the best move. Think carefully before playing."
    return coach, speak


def _blunder_check(result: AnalysisResult, san: str, score_label: str) -> tuple[str, str]:
    if result.evaluation <= -2.0:
        coach = f"Warning: the position is {score_label}. Consider {san} to improve."
        speak = f"Careful — you may be in trouble. {san} is the best defensive move."
    elif result.evaluation <= -0.5:
        coach = f"Slight disadvantage. Best try: {san}."
        speak = f"You're slightly worse. Try {san}."
    else:
        coach = f"Position looks fine. Best continuation: {san}."
        speak = f"You're doing well. Continue with {san}."
    return coach, speak


def _opening_coach(result: AnalysisResult, san: str, score_label: str) -> tuple[str, str]:
    coach = (
        f"Opening move: {san}. "
        f"This keeps the position {score_label}. "
        "Focus on development, center control, and king safety."
    )
    speak = f"Play {san}. Develop your pieces and control the center."
    return coach, speak


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_coaching_text(
    result: AnalysisResult,
    fen: str,
    mode: CoachMode,
    skill_level: int,
) -> AnalysisResult:
    """
    Mutates (and returns) `result` by populating coachText and speakText.
    """
    san = _san_from_uci(fen, result.bestMove)
    score_label = _score_label(result.evaluation)

    if mode == CoachMode.CASUAL:
        coach, speak = _casual_coach(result, san, score_label)
    elif mode == CoachMode.STUDY:
        coach, speak = _study_coach(result, san, score_label, fen)
    elif mode == CoachMode.PUZZLE:
        coach, speak = _puzzle_coach(result, san)
    elif mode == CoachMode.BLUNDER_CHECK:
        coach, speak = _blunder_check(result, san, score_label)
    elif mode == CoachMode.OPENING:
        coach, speak = _opening_coach(result, san, score_label)
    else:
        coach, speak = _casual_coach(result, san, score_label)

    # Skill-level disclaimer for weaker engines
    if skill_level < 10:
        coach += f" (Analysis at skill level {skill_level}.)"

    result.coachText = coach
    result.speakText = speak
    return result
