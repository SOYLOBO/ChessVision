"""
Vision Stage 4-6 replacement — LLM Vision FEN extraction.

Sends the warped top-down board image to a vision LLM (local Ollama or
Gemini API) and asks it to return the FEN board string directly.
"""
from __future__ import annotations
import base64
import logging
import re
import time as _time
import cv2
import numpy as np

logger = logging.getLogger(__name__)

_last_call_time = 0.0
_last_result: str | None = None
MIN_INTERVAL = 2.0  # seconds between LLM calls


PROMPT = """You are a chess position analyzer. You are looking at a top-down photo of a physical chess board.

The image shows the board from white's perspective: rank 8 (black's back rank) is at the top, rank 1 (white's back rank) is at the bottom. File 'a' is on the left, file 'h' is on the right.

Identify every piece on the board and output ONLY the FEN board string (the part before the first space). Use standard FEN notation:
- Uppercase for white pieces: K Q R B N P
- Lowercase for black pieces: k q r b n p
- Numbers for consecutive empty squares
- '/' to separate ranks (rank 8 first, rank 1 last)

For the standard starting position, the correct FEN board string is:
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR

Rules:
- There must be exactly 1 white king (K) and 1 black king (k)
- Pawns cannot be on rank 1 or rank 8
- Each rank must account for exactly 8 squares
- Look carefully at piece shapes: kings have a cross, queens have a crown/corona, rooks are castle-shaped, bishops have a pointed top, knights look like horses, pawns are small and round

Output ONLY the FEN board string, nothing else. No explanation, no spaces, no extra text."""


def _extract_fen(raw: str) -> str | None:
    """Extract a valid FEN board string from LLM response text."""
    raw = raw.strip()
    fen_match = re.search(r'[rnbqkpRNBQKP1-8/]{15,}', raw)
    if not fen_match:
        logger.warning("LLM returned no valid FEN pattern: %r", raw[:200])
        return None
    board_fen = fen_match.group(0)
    if board_fen.count('/') != 7:
        logger.warning("FEN has wrong rank count: %r", board_fen)
        return None
    return board_fen


def _call_ollama(img_b64: str, ollama_url: str, model: str) -> str | None:
    """Call local Ollama with vision model."""
    import urllib.request
    import json

    payload = json.dumps({
        "model": model,
        "prompt": PROMPT,
        "images": [img_b64],
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return _extract_fen(data.get("response", ""))
    except Exception as exc:
        logger.error("Ollama call failed: %s", exc)
        return None


def _call_gemini(img_b64: str) -> str | None:
    """Call Gemini API."""
    from app.core.config import settings
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content([
        {"mime_type": "image/jpeg", "data": img_b64},
        PROMPT,
    ])
    return _extract_fen(response.text)


def classify_full_frame(frame: np.ndarray) -> str | None:
    """
    Send the full camera frame to a vision LLM. Let the model find the board
    and identify all pieces. No corner pinning or perspective warp needed.
    """
    return classify_with_gemini(frame)


def classify_with_gemini(warped: np.ndarray) -> str | None:
    """
    Send board image to vision LLM, return FEN board string or None.
    Uses Ollama (local) if OLLAMA_URL is set, otherwise falls back to Gemini API.
    Throttled to one call per MIN_INTERVAL seconds.
    """
    global _last_call_time, _last_result

    now = _time.monotonic()
    if now - _last_call_time < MIN_INTERVAL and _last_result is not None:
        return _last_result

    _, buf = cv2.imencode(".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 95])
    img_b64 = base64.b64encode(buf).decode()

    from app.core.config import settings

    try:
        if settings.OLLAMA_URL:
            result = _call_ollama(img_b64, settings.OLLAMA_URL, settings.OLLAMA_MODEL)
        elif settings.GEMINI_API_KEY:
            result = _call_gemini(img_b64)
        else:
            logger.error("No vision LLM configured (set OLLAMA_URL or GEMINI_API_KEY)")
            return None

        _last_call_time = now
        if result:
            logger.info("LLM classified board: %s", result)
            _last_result = result
        return result or _last_result

    except Exception as exc:
        logger.error("LLM classification failed: %s", exc)
        _last_call_time = now
        return _last_result
