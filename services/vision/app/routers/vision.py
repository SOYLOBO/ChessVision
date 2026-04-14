"""
ChessMate AI – Vision Service Routers

POST /scan-frame     Primary endpoint (preferred)
POST /analyze-frame  Deprecated alias — remove once all callers migrated to /scan-frame
GET  /health
"""
from __future__ import annotations
import logging
import traceback
from fastapi import APIRouter, HTTPException
from app.models.vision import AnalyzeFrameRequest, VisionResult
from app.core.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()
health_router = APIRouter()


async def _run(body: AnalyzeFrameRequest) -> VisionResult:
    try:
        return run_pipeline(
            image_b64           = body.image_b64,
            last_known_good_fen = body.last_known_good_fen,
            previous_fen        = body.previous_fen,
            debug               = body.debug,
            pinned_corners      = body.pinned_corners,
            white_side          = body.white_side,
        )
    except Exception as exc:
        logger.error("Pipeline exception:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/scan-frame", response_model=VisionResult)
async def scan_frame(body: AnalyzeFrameRequest) -> VisionResult:
    """
    Primary vision endpoint.
    Set debug=true in the request body to receive annotated debug images
    (contour_overlay, rectified_board, grid_overlay, occupancy_map) in the response.
    """
    return await _run(body)


# Deprecated alias — kept for backwards compatibility with existing callers.
# Remove once VisionClaw and all consumers have migrated to POST /scan-frame.
@router.post("/analyze-frame", response_model=VisionResult, include_in_schema=False)
async def analyze_frame_alias(body: AnalyzeFrameRequest) -> VisionResult:
    return await _run(body)


@health_router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "vision"}
