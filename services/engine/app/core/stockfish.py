"""
Engine Service – Stockfish UCI wrapper.

Maintains a single long-lived Stockfish subprocess and exposes a
thread-safe `analyze()` method used by the analysis router.
"""

import threading
import subprocess
from typing import Optional

from app.core.config import settings
from app.models.analysis import MoveInfo, AnalysisResult


class StockfishError(RuntimeError):
    """Raised when communication with Stockfish fails."""


class StockfishEngine:
    """Persistent UCI subprocess wrapper (one instance per app lifetime)."""

    def __init__(self, path: str = settings.STOCKFISH_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._proc = subprocess.Popen(
            [self._path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._wait_for("uciok")
        self._send("isready")
        self._wait_for("readyok")

    def stop(self) -> None:
        if self._proc:
            try:
                self._send("quit")
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
            self._proc = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        fen: str,
        skill_level: int = 20,
        depth: int = settings.DEFAULT_DEPTH,
        multi_pv: int = settings.DEFAULT_MULTI_PV,
    ) -> AnalysisResult:
        with self._lock:
            return self._run_analysis(fen, skill_level, depth, multi_pv)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_analysis(
        self,
        fen: str,
        skill_level: int,
        depth: int,
        multi_pv: int,
    ) -> AnalysisResult:
        self._send(f"setoption name Skill Level value {skill_level}")
        self._send(f"setoption name MultiPV value {multi_pv}")
        self._send("ucinewgame")
        self._send(f"position fen {fen}")
        self._send(f"go depth {depth}")

        lines = self._collect_until("bestmove")

        best_move = self._parse_bestmove(lines)
        top_moves = self._parse_multipv(lines, multi_pv)
        evaluation = top_moves[0].score if top_moves else 0.0
        principal_variation = top_moves[0].pv if top_moves else []

        return AnalysisResult(
            bestMove=best_move,
            evaluation=evaluation,
            topMoves=top_moves,
            principalVariation=principal_variation,
        )

    # ------------------------------------------------------------------
    # Low-level UCI I/O
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> None:
        if not self._proc or self._proc.stdin is None:
            raise StockfishError("Stockfish process not running.")
        self._proc.stdin.write(cmd + "\n")
        self._proc.stdin.flush()

    def _readline(self) -> str:
        if not self._proc or self._proc.stdout is None:
            raise StockfishError("Stockfish process not running.")
        line = self._proc.stdout.readline()
        if not line:
            raise StockfishError("Stockfish process closed unexpectedly.")
        return line.rstrip()

    def _wait_for(self, token: str) -> None:
        while True:
            line = self._readline()
            if line.startswith(token):
                return

    def _collect_until(self, stop_token: str) -> list[str]:
        lines: list[str] = []
        while True:
            line = self._readline()
            lines.append(line)
            if line.startswith(stop_token):
                return lines

    # ------------------------------------------------------------------
    # UCI output parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bestmove(lines: list[str]) -> str:
        for line in reversed(lines):
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
        return ""

    @staticmethod
    def _parse_multipv(lines: list[str], multi_pv: int) -> list[MoveInfo]:
        """
        Collect the final `info depth ... multipv N ...` line for each PV slot.
        We only keep the last (deepest) report per multipv index.
        """
        pv_map: dict[int, MoveInfo] = {}

        for line in lines:
            if not line.startswith("info") or "multipv" not in line:
                continue
            if "pv" not in line:
                continue

            parts = line.split()
            try:
                mp_idx = int(parts[parts.index("multipv") + 1])
            except (ValueError, IndexError):
                continue

            # Score: cp or mate
            score: float = 0.0
            if "score" in parts:
                s_idx = parts.index("score")
                score_type = parts[s_idx + 1] if s_idx + 1 < len(parts) else ""
                score_val = parts[s_idx + 2] if s_idx + 2 < len(parts) else "0"
                try:
                    raw = int(score_val)
                    if score_type == "cp":
                        score = raw / 100.0
                    elif score_type == "mate":
                        # Positive: mate for side to move; negative: being mated
                        score = 999.0 if raw > 0 else -999.0
                except ValueError:
                    pass

            # PV moves
            pv: list[str] = []
            if "pv" in parts:
                pv_start = parts.index("pv") + 1
                pv = parts[pv_start:]

            best = pv[0] if pv else ""
            pv_map[mp_idx] = MoveInfo(move=best, score=score, pv=pv)

        # Return sorted by multipv index (1-based), up to multi_pv count
        return [pv_map[i] for i in sorted(pv_map) if i <= multi_pv]
