"""POST /api/upload — receive a room photo + chosen style, analyse it, and
return the analysis plus the follow-up questions."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import get_settings
from ..schemas import VALID_STYLES, UploadResponse
from ..services import claude_service
from ..services.errors import ServiceError
from ..services.pipeline import clean_room_size, read_photo
from ..store import new_session

router = APIRouter(prefix="/api", tags=["upload"])
settings = get_settings()


# Plain `def` (not async): FastAPI runs it in a worker thread, so the blocking
# Claude call doesn't stall every other request (e.g. image loads) meanwhile.
@router.post("/upload", response_model=UploadResponse)
def upload_room(
    request: Request,
    style: str = Form(...),
    room_size: str = Form(""),
    image: UploadFile = File(...),
):
    if style not in VALID_STYLES:
        raise HTTPException(422, f"Style must be one of: {', '.join(VALID_STYLES)}.")

    photo, fname = read_photo(image)
    # Root-relative on purpose: the frontend prefixes its API base, which keeps
    # the scheme right behind an HTTPS proxy (url_for would yield http://).
    image_url = request.app.url_path_for("serve_upload", filename=fname)

    try:
        analysis, mock, _ = claude_service.analyze_room(
            photo.data, photo.media_type, style, clean_room_size(room_size)
        )
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)
    questions, _, _ = claude_service.generate_questions(analysis, style)

    session_id = new_session(
        {
            "style": style,
            "image_filename": fname,
            "image_size": photo.size,
            "image_url": image_url,
            "analysis": analysis.model_dump(),
            "questions": [q.model_dump() for q in questions],
            "answers": [],
            "mock": mock,
            "warnings": [],
        }
    )

    return UploadResponse(
        session_id=session_id,
        style=style,
        image_url=image_url,
        analysis=analysis,
        questions=questions,
        mock=mock,
        warnings=[],
    )
