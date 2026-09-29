"""GET /api/session/{session_id} — full state for a session (debug / refresh)."""
from fastapi import APIRouter, HTTPException

from ..store import get_session

router = APIRouter(prefix="/api", tags=["session"])


@router.get("/session/{session_id}")
async def read_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Unknown session_id.")
    return session
