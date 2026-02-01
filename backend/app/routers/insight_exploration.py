"""
Insight Exploration API: forwards user query to Planning + Data agents.
Streams: query plan (markdown), progress at each step, final answer.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import InsightExplorationQuery
from ..adk_agent import run_insight_query_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insight-exploration", tags=["insight-exploration"])


async def _ndjson_stream(query: str, db: Session):
    """Yield NDJSON lines (one JSON object per line)."""
    async for chunk in run_insight_query_stream(query, db):
        yield json.dumps(chunk, ensure_ascii=False) + "\n"


@router.post("/query")
async def post_query(
    body: InsightExplorationQuery,
    db: Session = Depends(get_db),
):
    """Stream query plan (markdown), progress at each step, then final answer. NDJSON format."""
    query = (body.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required and cannot be empty")
    return StreamingResponse(
        _ndjson_stream(query, db),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
