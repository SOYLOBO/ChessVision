"""
Engine Service – Analysis router.

POST /analyze-position
"""

from fastapi import APIRouter, Request, HTTPException
from app.models.analysis import AnalyzeRequest, AnalysisResult
from app.coaching.templates import build_coaching_text
from app.core.config import settings
from app.core.stockfish import StockfishError

router = APIRouter()


@router.post("", response_model=AnalysisResult)
async def analyze_position(body: AnalyzeRequest, request: Request) -> AnalysisResult:
    engine = request.app.state.engine

    depth = body.depth or settings.DEFAULT_DEPTH
    multi_pv = body.multiPv or settings.DEFAULT_MULTI_PV

    try:
        result = engine.analyze(
            fen=body.fen,
            skill_level=body.skillLevel,
            depth=depth,
            multi_pv=multi_pv,
        )
    except StockfishError as exc:
        raise HTTPException(status_code=503, detail=f"Engine error: {exc}") from exc

    result = build_coaching_text(
        result=result,
        fen=body.fen,
        mode=body.mode,
        skill_level=body.skillLevel,
    )

    return result
