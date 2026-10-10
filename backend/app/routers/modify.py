"""POST /api/modify — the "Modify Existing Room" flow.

A single request: a photo of an already-furnished room, one free-text
instruction describing the change, and a budget. It assesses the room
(including what to keep, replace or remove), plans the change, renders it
onto the photo with an architecture check, and builds the shopping list —
mirroring /api/generate's response shape so the frontend's ResultView works
unchanged for either flow.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import get_settings
from ..schemas import VALID_BUDGETS, GenerateResponse, RecapItem
from ..services import claude_service
from ..services.errors import ServiceError
from ..services.pipeline import (
    STRUCTURE_WARNING,
    clean_room_size,
    read_photo,
    render_checked,
    save_render,
    shopping,
)
from ..store import new_session

router = APIRouter(prefix="/api", tags=["modify"])
settings = get_settings()

_MAX_INSTRUCTION_LEN = 600
# Product-catalogue style tags to lean on when matching furniture — the modify
# flow has no target style of its own, so this is just a default for scoring.
_MATCH_STYLE_FALLBACK = "Modern"


# Plain `def` so the slow provider calls run in a worker thread (see upload.py).
@router.post("/modify", response_model=GenerateResponse)
def modify_room(
    request: Request,
    instruction: str = Form(...),
    budget: str = Form(...),
    room_size: str = Form(""),
    image: UploadFile = File(...),
):
    instruction = (instruction or "").strip()[:_MAX_INSTRUCTION_LEN]
    if not instruction:
        raise HTTPException(422, "Please describe the change you'd like made.")
    if budget not in VALID_BUDGETS:
        raise HTTPException(422, f"Budget must be one of: {', '.join(VALID_BUDGETS)}.")

    photo, fname = read_photo(image)
    original_image_url = request.app.url_path_for("serve_upload", filename=fname)

    warnings: list[str] = []
    try:
        analysis, _, _ = claude_service.analyze_room(
            photo.data, photo.media_type, None, clean_room_size(room_size)
        )
        prompt, planned, _, _ = claude_service.build_modify_prompt(analysis, instruction, budget)
        image_result, check = render_checked(
            prompt, _MATCH_STYLE_FALLBACK, analysis, photo.data, photo.media_type, photo.size
        )
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)

    if check.status == "mismatch":
        warnings.append(STRUCTURE_WARNING.format(issues="; ".join(check.issues)))

    gen_fname = save_render(image_result)
    generated_image_url = request.app.url_path_for("serve_generated", filename=gen_fname)

    matches, note, total, recs, rec_note, rec_total = shopping(
        planned, prompt, _MATCH_STYLE_FALLBACK, budget, analysis
    )

    recap = [
        RecapItem(id="instruction", kind="instruction", question="Requested change", answer=instruction),
        RecapItem(id="budget", kind="budget", question="Budget", answer=budget),
    ]

    mock = image_result.mock or not (settings.anthropic_ready and settings.openai_ready)

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
            "structure_check": check.model_dump(),
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
        product_matches_note=note,
        recommendations=recs,
        recommendations_total=rec_total,
        recommendations_note=rec_note,
        recap=recap,
        estimated_total=total,
        mock=mock,
        warnings=warnings,
        original_image_url=original_image_url,
        analysis=analysis,
        structure_check=check,
    )
