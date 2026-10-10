"""Claude-powered steps: room analysis (incl. architecture inventory and
keep/replace verdicts on existing furniture), the redesign plan + image
prompt, and the structure check that compares a render with the original.

With an API key configured every step is a real call and a failure raises a
ServiceError the UI can show and retry — sample data is only ever used when
no key is configured (or FORCE_MOCK is on). The follow-up questions are
built in code from the analysis, so they are identical from run to run.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

from ..config import get_settings
from ..schemas import (
    ROOM_SIZES,
    VALID_ACTIONS,
    VALID_BUDGETS,
    FurnitureItem,
    Question,
    RoomAnalysis,
    RoomStructure,
    StructureCheck,
)
from .errors import ServiceError, run_real

settings = get_settings()

_client = None  # lazily created so importing this module never needs the SDK/key


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.anthropic_timeout,
            max_retries=1,
        )
    return _client


# Opus 5.5 always thinks before answering, and thinking tokens count toward
# max_tokens — a tight cap truncates the JSON mid-string. This is a ceiling,
# not a target: the visible replies here are still short.
_MAX_TOKENS = 16000

CATEGORIES = (
    "sofa, armchair, coffee table, side table, dining table, dining chair, rug, "
    "floor lamp, table lamp, pendant light, console, bookshelf, sideboard, bench, "
    "ottoman, curtains, plant, wall art, mirror, throw pillow, vase, storage basket, "
    "bed, wardrobe, desk, tv, decor"
)


def _extract_json(text: str) -> Any:
    """Claude usually returns clean JSON; strip code fences / prose just in case."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start > 0:
        text = text[start:]
    if not text:
        raise ValueError("empty response from model")
    return json.loads(text)


def _text_of(resp) -> str:
    stop = getattr(resp, "stop_reason", None)
    if stop == "refusal":
        raise ServiceError(
            "The design service declined to process this photo. Please try a different one.",
            status_code=422, kind="refusal",
        )
    if stop == "max_tokens":
        raise ValueError("model response was cut off at max_tokens")
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _ask_json(system: str, content: Any) -> Any:
    resp = _get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return _extract_json(_text_of(resp))


def _image_block(data: bytes, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }


def _clean_items(raw: list, *, allowed: tuple[str, ...]) -> list[FurnitureItem]:
    items = []
    for it in raw or []:
        item = FurnitureItem(**{k: ("" if v is None else str(v)) for k, v in it.items() if k in FurnitureItem.model_fields})
        action = item.action.strip().lower()
        item.action = action if action in allowed else ""
        if item.name or item.category:
            items.append(item)
    return items


# ===========================================================================
# 1. Analyse the uploaded room photo
# ===========================================================================
ANALYSIS_SYSTEM = (
    "You are an experienced interior designer assessing a photo of a room.\n"
    "Report only what is actually visible in the photo. Never infer rooms, "
    "stairs, windows or doors that are outside the frame.\n\n"
    "Respond with ONLY a JSON object, no prose:\n"
    "{\n"
    '  "room_type": str,\n'
    '  "summary": str,  // 1-2 sentences on size and feel\n'
    '  "size_class": "small"|"medium"|"large",  // small <= ~120 sq ft, large >= ~250 sq ft\n'
    '  "size_estimate": str,  // e.g. "about 110 sq ft (roughly 10 x 11 ft)"\n'
    '  "structure": {  // fixed architecture, described by where it sits in the frame\n'
    '    "windows": [str],  // ONE entry per window, e.g. "left wall: pair of tall white double-hung windows"\n'
    '    "doors": [str],  // one entry per door, doorway or opening\n'
    '    "stairs": str,  // "" if no staircase is visible\n'
    '    "other_fixed": [str]  // beams, columns, fireplace, built-ins, ceiling fan, AC unit\n'
    "  },\n"
    '  "existing_furniture": [{\n'
    '    "name": str, "category": str, "description": str, "color": str,\n'
    '    "size": str,  // rough footprint, e.g. "200 x 90 cm"\n'
    '    "action": "keep"|"replace"|"remove",\n'
    '    "reason": str  // ONE short sentence tied to THIS room\n'
    "  }],\n"
    '  "layout_notes": str,\n'
    '  "lighting": str,\n'
    '  "detected_colors": [str]\n'
    "}\n\n"
    "How to judge each existing piece (be decisive, like a designer on site):\n"
    "- Scale: is it the right size for this room? A 3-seater plus a 2-seater "
    "in a 100 sq ft room is too much seating — keep one, remove the other.\n"
    "- Circulation: main walkways need about 75 cm clear; doors and windows "
    "must not be blocked.\n"
    "- In a SMALL room (about 120 sq ft or less) judge strictly: a sofa wider "
    "than about 160 cm, a coffee table over 90 cm, or any second sofa is "
    "oversized and must be replace or remove, never keep. Judge fit only; "
    "ignore what a replacement would cost.\n"
    "- Function and condition: does it earn its floor space?\n"
    "- keep = it suits the room as is. replace = the room needs this kind of "
    "piece but this one is the wrong size or shape. remove = the room is "
    "better without it.\n"
    "- Group small accessories (cushions, bowls, books) into at most two entries.\n"
    f"Use lowercase categories from: {CATEGORIES}."
)


def analyze_room(
    image_bytes: bytes, media_type: str, style: str | None, room_size: str = ""
) -> tuple[RoomAnalysis, bool, str | None]:
    """Analyse a room photo. ``style`` is the target style for the "New Room
    Design" flow (``None`` for "Modify Existing Room"). ``room_size`` is the
    user's own size choice (a ROOM_SIZES key) or "" to estimate from the photo."""
    if not settings.anthropic_ready:
        return _apply_user_size(_mock_analysis(style), room_size), True, None

    text = "Assess this room as it is now."
    if style:
        text += f" The owner wants to restyle it as {style}; weigh that when judging each piece."
    if room_size in ROOM_SIZES:
        text += (
            f" The owner states the room size is: {ROOM_SIZES[room_size]}. Treat that as "
            f'fact: set size_class to "{room_size}" and judge every piece against it.'
        )

    def _real() -> RoomAnalysis:
        data = _ask_json(ANALYSIS_SYSTEM, [_image_block(image_bytes, media_type), {"type": "text", "text": text}])
        data["existing_furniture"] = [
            i.model_dump() for i in _clean_items(data.get("existing_furniture"), allowed=("keep", "replace", "remove"))
        ]
        data["structure"] = RoomStructure(**(data.get("structure") or {})).model_dump()
        analysis = RoomAnalysis(**data)
        if analysis.size_class not in ROOM_SIZES:
            analysis.size_class = "medium"
        return analysis

    analysis = run_real(_real, provider="anthropic", what="analysing the photo")
    return _apply_user_size(analysis, room_size), False, None


def _apply_user_size(analysis: RoomAnalysis, room_size: str) -> RoomAnalysis:
    if room_size in ROOM_SIZES:
        analysis.size_class = room_size
        analysis.size_estimate = ROOM_SIZES[room_size]
        analysis.size_from_user = True
    return analysis


# ===========================================================================
# 2. Follow-up questions — fixed set, worded in code, hints from the analysis
# ===========================================================================
def _budget_question() -> Question:
    return Question(
        id="budget",
        prompt="What's your budget for new pieces?",
        kind="budget",
        options=list(VALID_BUDGETS),
        hint="Covers only what you'd buy — pieces you keep cost nothing.",
    )


def generate_questions(
    analysis: RoomAnalysis, style: str
) -> tuple[list[Question], bool, str | None]:
    """Four single-choice questions, always the same ones in the same order.
    Each has mutually exclusive options; only the hints change per room."""
    items = analysis.existing_furniture
    keep = sum(1 for f in items if f.action == "keep")
    change = sum(1 for f in items if f.action in ("replace", "remove"))

    if items:
        second = Question(
            id="scope", kind="scope",
            prompt="How much of the room should change?",
            options=["Light refresh", "Balanced update", "Full makeover"],
            hint=(
                f"Our read of your room: keep {keep} piece{'s' if keep != 1 else ''}, "
                f"change {change}. Balanced follows that advice."
            ),
        )
    else:
        second = Question(
            id="scope", kind="scope",
            prompt="How furnished should the room be?",
            options=["Essentials only", "Comfortably furnished", "Fully styled"],
            hint="The room looks empty, so everything here would be new.",
        )

    text = f"{analysis.layout_notes} {analysis.lighting}".lower()
    if analysis.size_class == "small":
        priority_hint = "This is a small room, so open floor space usually matters most."
    elif any(k in text for k in ("dim", "dark", "low light", "little natural")):
        priority_hint = "The room reads a little dark, so lighting is worth prioritising."
    else:
        priority_hint = "Pick the one thing the redesign should get right."

    colours = ", ".join(c for c in analysis.detected_colors[:3] if c)
    return [
        _budget_question(),
        second,
        Question(
            id="priority", kind="priorities",
            prompt="What matters most?",
            options=["Open floor space", "Storage", "Seating", "Lighting", "A cosier feel"],
            hint=priority_hint,
        ),
        Question(
            id="palette", kind="colors", optional=True,
            prompt="Which colour direction?",
            options=["Keep current colours", "Light and neutral", "Warm and earthy", "Cool and calm", "Bold accents"],
            hint=f"Right now the room is mostly {colours}." if colours else "",
        ),
    ], not settings.anthropic_ready, None


# ===========================================================================
# 3. Redesign plan + image prompt (both flows)
# ===========================================================================
EXTRA_REQUEST_ID = "additional_request"

PLAN_SYSTEM = (
    "You are an interior designer producing a redesign plan for a real room, "
    "plus a prompt for an AI image editor that will repaint the owner's own "
    "photo. You get a JSON assessment of the room (its size, fixed "
    "architecture, and each existing piece with a keep/replace/remove verdict) "
    "and the owner's brief.\n\n"
    "Respond with ONLY JSON:\n"
    "{\n"
    '  "image_prompt": str,  // one paragraph, <= 110 words\n'
    '  "planned_furniture": [{\n'
    '    "name": str, "category": str, "description": str, "color": str,\n'
    '    "size": str,  // footprint in cm, e.g. "140 x 80 cm"\n'
    '    "action": "keep"|"replace"|"remove"|"add",\n'
    '    "reason": str  // ONE short sentence\n'
    "  }]\n"
    "}\n\n"
    "Plan rules:\n"
    "- Account for EVERY existing piece exactly once, as keep, replace or "
    "remove. For replace, describe the NEW piece and say in reason what it "
    "replaces and why. Then list anything new as add.\n"
    "- Start from the verdicts in the assessment; change one only when the "
    "owner's brief requires it. If the owner gives a specific instruction, "
    "implement it literally.\n"
    "- Budget covers only replace + add pieces, in Indian Rupees. Typical "
    "prices: sofa 35-70k, armchair 10-25k, dining table 25-55k, bookshelf "
    "7-20k, coffee table 7-20k, rug 5-15k, lamp 3-8k, mirror 3-7k, wall art "
    "3-6k, curtains 3-6k, plant 2-4k, cushions 1-3k. Do not plan purchases "
    "that cannot fit the budget; if a piece should ideally be replaced but is "
    "unaffordable, keep it and say so in reason.\n"
    "- Wall-mounted pieces need a stretch of bare wall; never plan one over a "
    "window or door.\n"
    "- Everything must physically fit. Give every piece a realistic size and "
    "keep about 75 cm clear on walkways; never block a door or window.\n"
    "- SMALL rooms (about 120 sq ft or less): at most one sofa, no wider than "
    "a 2-seater (about 150 cm); no sectionals, no dining table for more than "
    "two, no coffee table over 90 cm (prefer nesting or a slim side table), "
    "storage that goes up the wall rather than across the floor, and no more "
    "than 3 new floor-standing pieces. Prefer removing to adding.\n"
    f"- Use lowercase categories from: {CATEGORIES}.\n\n"
    "image_prompt rules:\n"
    "- Describe ONLY furniture, decor, textiles, lamps, colours and finishes, "
    "and where each sits. Name kept pieces as unchanged and removed pieces as "
    "gone, leaving clear floor.\n"
    "- Wall art, mirrors and shelves go only on bare wall. Never place "
    "anything over, across or in front of a window or door; if the sofa sits "
    "under a window, nothing hangs above that sofa.\n"
    "- Do not describe, add or alter windows, doors, stairs, walls, ceiling, "
    "flooring layout or the camera view — those are locked separately."
)


def _plan(analysis: RoomAnalysis, brief: str, mock_fn) -> tuple[str, list[FurnitureItem], bool, str | None]:
    if not settings.anthropic_ready:
        prompt, items = mock_fn()
        return prompt, items, True, None

    def _real() -> tuple[str, list[FurnitureItem]]:
        data = _ask_json(
            PLAN_SYSTEM,
            f"Room assessment JSON:\n{analysis.model_dump_json(indent=2)}\n\nOwner's brief:\n{brief}",
        )
        prompt = str(data["image_prompt"]).strip()
        items = _clean_items(data.get("planned_furniture"), allowed=VALID_ACTIONS)
        if not prompt or not items:
            raise ValueError("plan was missing the image prompt or the furniture list")
        return prompt, items

    prompt, items = run_real(_real, provider="anthropic", what="planning the redesign")
    return prompt, items, False, None


def build_image_prompt(
    analysis: RoomAnalysis, style: str, answers: list[dict[str, str]], questions: list[Question] | None = None
) -> tuple[str, list[FurnitureItem], bool, str | None]:
    labels = {q.id: q.prompt for q in (questions or [])}
    lines = [f"- Target style: {style}"]
    for a in answers:
        qid = a.get("question_id", a.get("id", "?"))
        if qid == EXTRA_REQUEST_ID:
            lines.append(f"- Specific instruction from the owner (implement literally): {a['answer']}")
        else:
            lines.append(f"- {labels.get(qid, qid)} {a['answer']}")
    return _plan(analysis, "\n".join(lines), lambda: _mock_prompt(analysis, style, answers))


def build_modify_prompt(
    analysis: RoomAnalysis, instruction: str, budget: str | None
) -> tuple[str, list[FurnitureItem], bool, str | None]:
    brief = (
        f"- The room is already furnished and the owner wants this change: {instruction}\n"
        "- If that is specific, implement it literally; if it is general, use the "
        "verdicts in the assessment and good judgement.\n"
        "- Keep the room recognisably the same room; leave alone whatever the "
        "instruction and the verdicts don't touch.\n"
        f"- Budget for new pieces: {budget or 'not specified'}"
    )
    return _plan(analysis, brief, lambda: _mock_modify_prompt(analysis, instruction))


# ===========================================================================
# 4. Structure check — does the render still show the same room?
# ===========================================================================
VERIFY_SYSTEM = (
    "You are checking an AI-edited interior photo against the original. "
    "Image 1 is the ORIGINAL room, image 2 is the REDESIGN.\n"
    "Compare ONLY the fixed architecture: windows (how many, which wall, "
    "roughly where and how big), doors and openings, stairs, the walls and "
    "room shape, and the camera viewpoint.\n"
    "IGNORE furniture, decor, lamps, rugs, colours, lighting mood, curtains or "
    "blinds, wall art and mirrors (framed art or a mirror is not a window; a "
    "window partly hidden behind new furniture or curtains still counts as "
    "present).\n"
    "Report an issue only when you are confident an architectural element was "
    "added, removed, moved or changed into something else.\n"
    'Respond with ONLY JSON: {"consistent": bool, "issues": [str]} — each '
    "issue one short sentence saying what the redesign got wrong, e.g. "
    '"The window on the right wall was replaced by a blank wall panel."'
)


def verify_structure(original: bytes, render: bytes, structure: RoomStructure) -> StructureCheck:
    """Compare the render with the original. Never raises: if the check itself
    fails it reports ``skipped`` rather than blocking a finished render."""
    if not (settings.anthropic_ready and settings.verify_structure):
        return StructureCheck(status="skipped")
    from .image_prep import downscale_jpeg

    try:
        data = _ask_json(
            VERIFY_SYSTEM,
            [
                {"type": "text", "text": "Image 1 — ORIGINAL:"},
                _image_block(downscale_jpeg(original), "image/jpeg"),
                {"type": "text", "text": "Image 2 — REDESIGN:"},
                _image_block(downscale_jpeg(render), "image/jpeg"),
                {
                    "type": "text",
                    "text": "Architecture recorded from the original:\n"
                    + structure.model_dump_json(indent=2),
                },
            ],
        )
        issues = [str(i).strip() for i in (data.get("issues") or []) if str(i).strip()][:5]
        ok = bool(data.get("consistent")) and not issues
        return StructureCheck(status="passed" if ok else "mismatch", issues=[] if ok else issues)
    except Exception:  # noqa: BLE001 - the check is best-effort by design
        import logging

        logging.getLogger("interior_design_assistant").exception("Structure check failed; skipping it.")
        return StructureCheck(status="skipped")


# ===========================================================================
# Sample data — only used when no ANTHROPIC_API_KEY is configured
# ===========================================================================
def _mock_analysis(style: str | None) -> RoomAnalysis:
    return RoomAnalysis(
        room_type="living room",
        summary=(
            "A small living room that feels tight and a little dim. "
            "(Sample analysis — no ANTHROPIC_API_KEY is configured.)"
        ),
        size_class="small",
        size_estimate="about 110 sq ft (roughly 10 x 11 ft)",
        structure=RoomStructure(
            windows=["right wall: one large window"],
            doors=["back wall, far right: a single door"],
        ),
        existing_furniture=[
            FurnitureItem(name="Three-seat sofa", category="sofa", description="Fabric, sagging cushions", color="brown",
                          size="210 x 90 cm", action="replace", reason="Too long for a room this size; a 2-seater frees the walkway."),
            FurnitureItem(name="Two-seat sofa", category="sofa", description="Matching loveseat", color="brown",
                          size="150 x 90 cm", action="remove", reason="Two sofas crowd a 110 sq ft room."),
            FurnitureItem(name="Coffee table", category="coffee table", description="Scratched veneer", color="dark wood",
                          size="120 x 60 cm", action="replace", reason="Oversized for the remaining floor space."),
            FurnitureItem(name="Floor lamp", category="floor lamp", description="Basic torchiere", color="black",
                          size="30 x 30 cm", action="keep", reason="Small footprint and the room needs the light."),
            FurnitureItem(name="Area rug", category="rug", description="Sits off-centre", color="beige",
                          size="160 x 230 cm", action="keep", reason="Right scale once it is re-centred."),
        ],
        layout_notes="Sofa on the long wall, TV opposite; the walkway by the window is tight.",
        lighting="One window; on the dim side in the evening.",
        detected_colors=["brown", "beige", "off-white"],
    )


def _mock_prompt(
    analysis: RoomAnalysis, style: str, answers: list[dict[str, str]]
) -> tuple[str, list[FurnitureItem]]:
    extra = next((a.get("answer", "") for a in answers if a.get("question_id") == EXTRA_REQUEST_ID), "").strip()
    kept = [f.model_copy() for f in analysis.existing_furniture if f.action == "keep"]
    removed = [f.model_copy() for f in analysis.existing_furniture if f.action == "remove"]
    new = [
        FurnitureItem(name=f"{style} two-seat sofa", category="sofa", description="Compact, raised legs", color="neutral",
                      size="150 x 85 cm", action="replace", reason="Replaces the three-seater so the walkway stays clear."),
        FurnitureItem(name="Nesting coffee tables", category="coffee table", description="Pair that tucks away", color="wood",
                      size="60 x 60 cm", action="replace", reason="Replaces the oversized table."),
        FurnitureItem(name="Framed wall art", category="wall art", description="Set of two prints", color="neutral",
                      size="50 x 70 cm", action="add", reason="Adds interest without using floor space."),
        FurnitureItem(name="Floor plant", category="plant", description="Tall, in a woven basket", color="green",
                      size="35 x 35 cm", action="add", reason="Softens the corner by the window."),
    ]
    prompt = (
        f"Restyle the furniture in a {style} style: a compact two-seat sofa, nesting coffee tables, "
        f"framed prints and a tall plant. {', '.join(f.name for f in kept) or 'Existing lamp and rug'} "
        f"stay unchanged; {', '.join(f.name for f in removed) or 'surplus pieces'} removed, leaving clear floor. "
        f"{f'Also: {extra}. ' if extra else ''}Bright, tidy, natural daylight."
    )
    return prompt, kept + new + removed


def _mock_modify_prompt(analysis: RoomAnalysis, instruction: str) -> tuple[str, list[FurnitureItem]]:
    items = [f.model_copy() for f in analysis.existing_furniture]
    for f in items:
        f.action = f.action or "keep"
    prompt = (
        f'Apply this change exactly: "{instruction.strip()}". Keep every other piece of furniture as it is. '
        "Tidy styling, natural daylight."
    )
    return prompt, items
