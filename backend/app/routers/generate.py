"""POST /api/generate — turn the analysis + style + answers into a DALL-E
prompt, generate the redesigned image, and match the planned furniture against
the local product catalogue.

The generated image is always persisted under our own /media/generated/ path
(never a provider's ephemeral URL), so the before/after slider and the
download button work identically for the mock placeholder today and the real
DALL-E output once OPENAI_API_KEY is set — no frontend change needed either way.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from ..config import get_settings
from ..schemas import GenerateRequest, GenerateResponse, Question, RecapItem, RoomAnalysis
from ..services import claude_service, image_service, recommendation_service
from ..services.errors import ServiceError
from ..services.product_service import match_products
from ..services.upload_validate import sniff
from ..store import get_session, update_session

router = APIRouter(prefix="/api", tags=["generate"])
settings = get_settings()


def _load_upload(filename: str | None) -> tuple[bytes | None, str]:
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None, ""
    try:
        data = (settings.upload_dir / filename).read_bytes()
    except OSError:
        return None, ""
    sniffed = sniff(data)
    return (data, sniffed[0]) if sniffed else (None, "")


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
    warnings: list[str] = list(session.get("warnings", []))

    extra_request = (session.get("extra_request") or "").strip()
    prompt_answers = answers + (
        [{"question_id": claude_service.EXTRA_REQUEST_ID, "answer": extra_request}] if extra_request else []
    )

    # The user's own photo is the base the redesign is drawn on, so the room's
    # layout carries over. Uploads live on local disk, so a restart can lose it;
    # then we still render from the text prompt, but say so.
    source, source_type = _load_upload(session.get("image_filename"))
    if source is None:
        missing = "Your original photo wasn't available, so the redesign is based on the description only."
        if missing not in warnings:
            warnings.append(missing)

    try:
        prompt, planned, _mock_p, warn_p = claude_service.build_image_prompt(analysis, style, prompt_answers)
        image = image_service.generate_image(
            prompt, style, analysis.room_type, source_image=source, source_media_type=source_type
        )
    except ServiceError as se:
        raise HTTPException(se.status_code, se.user_message)

    if warn_p and warn_p not in warnings:
        warnings.append(warn_p)
    if image.warning and image.warning not in warnings:
        warnings.append(image.warning)

    ext = ".png" if "png" in image.content_type else ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    try:
        (settings.generated_dir / fname).write_bytes(image.data)
    except OSError:
        raise HTTPException(500, "Couldn't save the generated image on the server. Please try again.")
    image_url = request.app.url_path_for("serve_generated", filename=fname)

    budget = next((a["answer"] for a in answers if a["question_id"] == "budget"), None)
    matches, product_matches_note = match_products(planned, style=style, budget=budget)
    estimated_total = round(sum(m.price for m in matches), 2)
    recommendations, recommendations_note = recommendation_service.get_recommendations(prompt, budget=budget)
    recommendations_total = round(sum(r.price for r in recommendations), 2)

    answers_map = {a["question_id"]: a["answer"] for a in answers}
    recap = [
        RecapItem(id=q.id, kind=q.kind, question=q.prompt, answer=answers_map[q.id])
        for q in questions
        if q.id in answers_map
    ]
    if extra_request:
        recap.append(RecapItem(id="instruction", kind="instruction", question="Requested change", answer=extra_request))

    mock = image.mock or bool(warn_p) or not (settings.anthropic_ready and settings.openai_ready)

    update_session(
        req.session_id,
        {
            "image_prompt": prompt,
            "generated_image_url": image_url,
            "generated_filename": fname,
            "planned_furniture": [p.model_dump() for p in planned],
            "product_matches": [m.model_dump() for m in matches],
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
        product_matches_note=product_matches_note,
        recommendations=recommendations,
        recommendations_total=recommendations_total,
        recommendations_note=recommendations_note,
        recap=recap,
        estimated_total=estimated_total,
        mock=mock,
        warnings=warnings,
    )
