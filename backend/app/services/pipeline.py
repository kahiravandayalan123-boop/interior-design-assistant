"""Steps shared by /api/generate and /api/modify: take in a photo, render the
redesign with an architecture check, and build the shopping lists."""
from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, UploadFile

from ..config import get_settings
from ..schemas import (
    ROOM_SIZES,
    FurnitureItem,
    ProductMatch,
    ProductRecommendation,
    RoomAnalysis,
    StructureCheck,
    parse_budget_amount,
)
from . import claude_service, image_service, recommendation_service
from .image_prep import PhotoError, PreparedPhoto, prepare_photo
from .image_service import ImageResult
from .product_service import match_products
from .upload_validate import MAX_BYTES, MIN_BYTES, sniff

settings = get_settings()
logger = logging.getLogger("interior_design_assistant.pipeline")

STRUCTURE_WARNING = (
    "The AI render changed part of the room's architecture ({issues}) even after "
    "a second attempt. Treat the image as a furniture and styling guide only."
)


def read_photo(image: UploadFile) -> tuple[PreparedPhoto, str]:
    """Validate an upload, normalise it, save it. Returns (photo, filename)."""
    try:
        data = image.file.read()
    except Exception:  # noqa: BLE001 - malformed multipart / client disconnect
        raise HTTPException(400, "Could not read the uploaded file. Please try again.")
    if not data or len(data) < MIN_BYTES:
        raise HTTPException(422, "That file looks empty or truncated. Choose a real photo.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That image is larger than 10 MB. Please pick a smaller one.")
    if sniff(data) is None:
        raise HTTPException(
            415,
            "That doesn't look like a JPEG, PNG, or WebP image (the file may be "
            "corrupt or the wrong type). Please choose a different photo.",
        )
    try:
        photo = prepare_photo(data)
    except PhotoError as exc:
        raise HTTPException(422, str(exc))

    fname = f"{uuid.uuid4().hex}.jpg"
    try:
        (settings.upload_dir / fname).write_bytes(photo.data)
    except OSError:
        raise HTTPException(500, "Couldn't save the upload on the server. Please try again.")
    return photo, fname


def clean_room_size(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value if value in ROOM_SIZES else ""


def render_checked(
    prompt: str,
    style: str,
    analysis: RoomAnalysis,
    source: bytes | None,
    media_type: str,
    size: str | None,
) -> tuple[ImageResult, StructureCheck]:
    """Render, compare the result with the original's architecture, and
    re-render once with the specific faults called out if it drifted."""
    kwargs = dict(
        source_image=source, source_media_type=media_type,
        structure=analysis.structure if source else None, size=size,
    )
    image = image_service.generate_image(prompt, style, analysis.room_type, **kwargs)
    if image.mock or not source:
        return image, StructureCheck(status="skipped")

    check = claude_service.verify_structure(source, image.data, analysis.structure)
    if check.status != "mismatch":
        return image, check

    logger.warning("Structure mismatch on first render: %s", check.issues)
    try:
        retry = image_service.generate_image(
            prompt, style, analysis.room_type, fix_issues=check.issues, **kwargs
        )
    except Exception:  # noqa: BLE001 - keep the first render rather than fail the request
        logger.exception("Corrective re-render failed; keeping the first render.")
        check.attempts = 2
        return image, check

    second = claude_service.verify_structure(source, retry.data, analysis.structure)
    second.attempts = 2
    if second.status == "passed":
        second.status = "corrected"
        return retry, second
    if second.status == "skipped":
        return image, check
    logger.warning("Structure mismatch persisted after re-render: %s", second.issues)
    # Keep whichever attempt drifted less.
    return (retry, second) if len(second.issues) <= len(check.issues) else (image, check)


def save_render(image: ImageResult) -> str:
    fname = f"{uuid.uuid4().hex}{'.png' if 'png' in image.content_type else '.jpg'}"
    try:
        (settings.generated_dir / fname).write_bytes(image.data)
    except OSError:
        raise HTTPException(500, "Couldn't save the generated image on the server. Please try again.")
    return fname


def shopping(
    planned: list[FurnitureItem], prompt: str, style: str, budget: str | None, analysis: RoomAnalysis
) -> tuple[list[ProductMatch], str | None, float, list[ProductRecommendation], str | None, float]:
    """Shopping list for the pieces being bought, then optional extras from
    whatever budget is left — never a category the plan keeps or removes."""
    small = analysis.size_class == "small"
    matches, note = match_products(planned, style=style, budget=budget, small_room=small)
    total = round(sum(m.price for m in matches), 2)

    amount = parse_budget_amount(budget)
    remaining = None if amount is None else max(amount - total, 0.0)
    recs: list[ProductRecommendation] = []
    rec_note = None
    if remaining is None or remaining > 0:
        exclude = {p.category for p in planned} | {f.category for f in analysis.existing_furniture}
        exclude |= {m.category for m in matches}
        recs, rec_note = recommendation_service.get_recommendations(
            prompt, budget=None if remaining is None else str(remaining),
            top_k=4, exclude_categories=exclude, small_room=small,
        )
    return matches, note, total, recs, rec_note, round(sum(r.price for r in recs), 2)
