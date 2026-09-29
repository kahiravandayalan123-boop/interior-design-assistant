"""POST /api/modify — the "Modify Existing Room" flow.

Unlike /api/upload -> /api/chat -> /api/generate (style pick + adaptive Q&A),
this is a single request: a photo of an already-furnished room plus one
free-text instruction describing the change the user wants (general, like
"make it appealing", or specific, like "move the table near the window to be
near the bed instead") and a budget. It analyses the room, builds a redesign
prompt that implements that exact instruction, generates the image, and
matches products — mirroring /api/generate's response shape so the frontend's
ResultView works unchanged for either flow.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import get_settings
from ..schemas import VALID_BUDGETS, GenerateResponse, RecapItem
from ..services import claude_service, image_service, recommendation_service
from ..services.errors import ServiceError
from ..services.product_service import match_products
from ..services.upload_validate import MAX_BYTES, MIN_BYTES
from ..services.upload_validate import sniff as _sniff
from ..store import new_session

router = APIRouter(prefix="/api", tags=["modify"])
settings = get_settings()

_MAX_INSTRUCTION_LEN = 600
# Product-catalogue style tags to lean on when matching kept/added furniture —
# the modify flow has no target style of its own, so this is just a sensible
# default for scoring, not shown to the user.
_MATCH_STYLE_FALLBACK = "Modern"


# Plain `def` so the slow provider calls run in a worker thread (see upload.py).
@router.post("/modify", response_model=GenerateResponse)
def modify_room(
    request: Request,
    instruction: str = Form(...),
    budget: str = Form(...),
    image: UploadFile = File(...),
):
    instruction = (instruction or "").strip()[:_MAX_INSTRUCTION_LEN]
    if not instruction:
        raise HTTPException(422, "Please describe the change you'd like made.")
    if budget not in VALID_BUDGETS:
        raise HTTPException(422, f"Budget must be one of: {', '.join(VALID_BUDGETS)}.")

    try:
        data = image.file.read()
    except Exception:  # noqa: BLE001 - malformed multipart / client disconnect
        raise HTTPException(400, "Could not read the uploaded file. Please try again.")

    if not data or len(data) < MIN_BYTES:
        raise HTTPException(422, "That file looks empty or truncated. Choose a real photo.")
    if len(data) > MAX_BYTES:
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
    original_image_url = request.app.url_path_for("serve_upload", filename=fname)

    warnings: list[str] = []
    try:
        analysis, _mock_a, warn_a = claude_service.analyze_room(data, media_type, None)
        prompt, planned, _mock_p, warn_p = claude_service.build_modify_prompt(
            analysis, instruction, budget
        )
        image_result = image_service.generate_image(prompt, _MATCH_STYLE_FALLBACK, analysis.room_type)
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)

    for w in (warn_a, warn_p, image_result.warning):
        if w and w not in warnings:
            warnings.append(w)

    gen_ext = ".png" if "png" in image_result.content_type else ".jpg"
    gen_fname = f"{uuid.uuid4().hex}{gen_ext}"
    try:
        (settings.generated_dir / gen_fname).write_bytes(image_result.data)
    except OSError:
        raise HTTPException(500, "Couldn't save the generated image on the server. Please try again.")
    generated_image_url = request.app.url_path_for("serve_generated", filename=gen_fname)

    matches, product_matches_note = match_products(planned, style=_MATCH_STYLE_FALLBACK, budget=budget)
    estimated_total = round(sum(m.price for m in matches), 2)
    recommendations, recommendations_note = recommendation_service.get_recommendations(prompt, budget=budget)
    recommendations_total = round(sum(r.price for r in recommendations), 2)

    recap = [
        RecapItem(id="instruction", kind="instruction", question="Requested change", answer=instruction),
        RecapItem(id="budget", kind="budget", question="Budget", answer=budget),
    ]

    mock = image_result.mock or bool(warn_a or warn_p) or not (
        settings.anthropic_ready and settings.openai_ready
    )

    session_id = new_session(
        {
            "mode": "modify",
            "instruction": instruction,
            "budget": budget,
            "image_filename": fname,
            "image_url": original_image_url,
            "analysis": analysis.model_dump(),
            "image_prompt": prompt,
            "generated_image_url": generated_image_url,
            "generated_filename": gen_fname,
            "planned_furniture": [p.model_dump() for p in planned],
            "product_matches": [m.model_dump() for m in matches],
            "mock": mock,
            "warnings": warnings,
        }
    )

    return GenerateResponse(
        session_id=session_id,
        style="Custom",
        image_prompt=prompt,
        generated_image_url=generated_image_url,
        image_is_mock=image_result.mock,
        planned_furniture=planned,
        product_matches=matches,
        product_matches_note=product_matches_note,
        recommendations=recommendations,
        recommendations_total=recommendations_total,
        recommendations_note=recommendations_note,
        recap=recap,
        estimated_total=estimated_total,
        mock=mock,
        warnings=warnings,
        original_image_url=original_image_url,
    )
