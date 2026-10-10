"""POST /api/generate — turn the analysis + style + answers into a redesign
plan, render it onto the user's own photo (with an architecture check), and
build the shopping list for the pieces being bought.

The generated image is always persisted under our own /media/generated/ path
(never a provider's ephemeral URL), so the before/after slider and the
download button work without CORS or expiring links.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import get_settings
from ..schemas import GenerateRequest, GenerateResponse, Question, RecapItem, RoomAnalysis
from ..services import claude_service
from ..services.errors import ServiceError
from ..services.image_prep import size_of
from ..services.pipeline import STRUCTURE_WARNING, render_checked, save_render, shopping
from ..store import get_session, update_session

router = APIRouter(prefix="/api", tags=["generate"])
settings = get_settings()


def _load_upload(filename: str | None) -> bytes | None:
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    try:
        return (settings.upload_dir / filename).read_bytes()
    except OSError:
        return None


# Plain `def` so the slow provider calls run in a worker thread (see upload.py).
@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, request: Request):
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(
            404, "That session wasn't found — it may have expired. Please start over."
        )

    questions = [Question(**q) for q in session.get("questions", [])]
    answers = session.get("answers", [])
    answered_ids = {a["question_id"] for a in answers}
    unanswered = [q for q in questions if not q.optional and q.id not in answered_ids]
    if unanswered:
        raise HTTPException(
            409,
            "Please answer the follow-up questions before generating: "
            + "; ".join(q.prompt for q in unanswered),
        )

    analysis = RoomAnalysis(**session["analysis"])
    style = session["style"]
    warnings: list[str] = []

    extra_request = (session.get("extra_request") or "").strip()
    prompt_answers = answers + (
        [{"question_id": claude_service.EXTRA_REQUEST_ID, "answer": extra_request}] if extra_request else []
    )

    # The user's own photo is the base the redesign is drawn on. Uploads live
    # on local disk, so without it we refuse rather than invent a room from text.
    source = _load_upload(session.get("image_filename"))
    if source is None and settings.openai_ready:
        raise HTTPException(
            404, "Your photo is no longer on the server (it may have restarted). Please start over."
        )

    modify = session.get("mode") == "modify"
    instruction = session.get("instruction") or ""
    budget = next((a["answer"] for a in answers if a["question_id"] == "budget"), None)
    # The modify flow has no target style; "Modern" is only a scoring default.
    match_style = "Modern" if modify else style

    try:
        if modify:
            prompt, planned, _, _ = claude_service.build_modify_prompt(
                analysis, instruction, budget, prompt_answers, questions
            )
        else:
            prompt, planned, _, _ = claude_service.build_image_prompt(analysis, style, prompt_answers, questions)
        image, check = render_checked(
            prompt, match_style, analysis, source, "image/jpeg",
            session.get("image_size") or (size_of(source) if source else None),
        )
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)

    if check.status == "mismatch":
        warnings.append(STRUCTURE_WARNING.format(issues="; ".join(check.issues)))

    fname = save_render(image)
    image_url = request.app.url_path_for("serve_generated", filename=fname)

    matches, note, total, recs, rec_note, rec_total = shopping(planned, prompt, match_style, budget, analysis)

    answers_map = {a["question_id"]: a["answer"] for a in answers}
    recap = [
        RecapItem(id=q.id, kind=q.kind, question=q.prompt, answer=answers_map[q.id])
        for q in questions
        if q.id in answers_map
    ]
    if modify:
        recap.insert(0, RecapItem(id="instruction", kind="instruction", question="Requested change", answer=instruction))
    elif extra_request:
        recap.append(RecapItem(id="instruction", kind="instruction", question="Requested change", answer=extra_request))

    mock = image.mock or not (settings.anthropic_ready and settings.openai_ready)

    update_session(
        req.session_id,
        {
            "image_prompt": prompt,
            "generated_image_url": image_url,
            "generated_filename": fname,
            "planned_furniture": [p.model_dump() for p in planned],
            "product_matches": [m.model_dump() for m in matches],
            "structure_check": check.model_dump(),
            "warnings": warnings,
        },
    )

    return GenerateResponse(
        session_id=req.session_id,
        style=style,
        image_prompt=prompt,
        generated_image_url=image_url,
        image_is_mock=image.mock,
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
        analysis=analysis,
        structure_check=check,
    )
