"""POST /api/upload — receive a room photo + chosen style, analyse it, and
return the analysis plus the first set of adaptive follow-up questions."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import get_settings
from ..schemas import VALID_STYLES, UploadResponse
from ..services import claude_service
from ..services.errors import ServiceError
from ..services.upload_validate import MAX_BYTES as _MAX_BYTES
from ..services.upload_validate import MIN_BYTES as _MIN_BYTES
from ..services.upload_validate import sniff as _sniff
from ..store import new_session

router = APIRouter(prefix="/api", tags=["upload"])
settings = get_settings()


# Plain `def` (not async): FastAPI runs it in a worker thread, so the blocking
# Claude call doesn't stall every other request (e.g. image loads) meanwhile.
@router.post("/upload", response_model=UploadResponse)
def upload_room(
    request: Request,
    style: str = Form(...),
    image: UploadFile = File(...),
):
    if style not in VALID_STYLES:
        raise HTTPException(422, f"Style must be one of: {', '.join(VALID_STYLES)}.")

    try:
        data = image.file.read()
    except Exception:  # noqa: BLE001 - malformed multipart / client disconnect
        raise HTTPException(400, "Could not read the uploaded file. Please try again.")

    if not data or len(data) < _MIN_BYTES:
        raise HTTPException(422, "That file looks empty or truncated. Choose a real photo.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, "That image is larger than 10 MB. Please pick a smaller one.")

    sniffed = _sniff(data)
    if sniffed is None:
        raise HTTPException(
            415,
            "That doesn't look like a JPEG, PNG, or WebP image (the file may be "
            "corrupt or the wrong type). Please choose a different photo.",
        )
    media_type, ext = sniffed

    fname = f"{uuid.uuid4().hex}{ext}"
    try:
        (settings.upload_dir / fname).write_bytes(data)
    except OSError:
        raise HTTPException(500, "Couldn't save the upload on the server. Please try again.")
    # Root-relative on purpose: the frontend prefixes its API base, which keeps
    # the scheme right behind an HTTPS proxy (url_for would yield http://).
    image_url = request.app.url_path_for("serve_upload", filename=fname)

    warnings: list[str] = []
    try:
        analysis, _mock_a, warn_a = claude_service.analyze_room(data, media_type, style)
        questions, _mock_q, warn_q = claude_service.generate_questions(analysis, style)
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)

    for w in (warn_a, warn_q):
        if w and w not in warnings:
            warnings.append(w)
    mock = bool(warn_a or warn_q) or not settings.anthropic_ready

    session_id = new_session(
        {
            "style": style,
            "image_filename": fname,
            "image_url": image_url,
            "analysis": analysis.model_dump(),
            "questions": [q.model_dump() for q in questions],
            "answers": [],
            "mock": mock,
            "warnings": warnings,
        }
    )

    return UploadResponse(
        session_id=session_id,
        style=style,
        image_url=image_url,
        analysis=analysis,
        questions=questions,
        mock=mock,
        warnings=warnings,
    )
