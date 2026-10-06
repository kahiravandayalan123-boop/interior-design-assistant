"""Claude-powered steps: room-photo analysis, adaptive follow-up questions, and
building the text-to-image prompt for the redesign.

Each step tries the real Anthropic call (when a key is configured) and falls
back to a deterministic mock on failure. Because these run at upload time and
must never dead-end the demo, even transient errors degrade to the mock — the
returned ``warning`` string lets the UI show a soft notice explaining why.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings
from ..schemas import VALID_BUDGETS, FurnitureItem, Question, RoomAnalysis
from .errors import run_or_degrade

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
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise ValueError("model response was cut off at max_tokens")
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


# ===========================================================================
# 1. Analyse the uploaded room photo
# ===========================================================================
ANALYSIS_SYSTEM = (
    "You are an interior designer analysing a photo of a room. "
    "Identify the room type, existing furniture and large objects, the layout, "
    "and the lighting. Respond with ONLY a JSON object, no prose, matching:\n"
    "{\n"
    '  "room_type": str,\n'
    '  "summary": str,  // 1-2 sentences, mention size/feel\n'
    '  "existing_furniture": [{"name": str, "category": str, "description": str, "color": str}],\n'
    '  "layout_notes": str,  // note if the room reads small / tight / open\n'
    '  "lighting": str,  // note if it reads dark / dim / bright\n'
    '  "detected_colors": [str]\n'
    "}\n"
    "Use lowercase generic categories like: sofa, coffee table, rug, floor lamp, "
    "table lamp, armchair, dining chair, dining table, bookshelf, console, "
    "sideboard, side table, curtains, plant, wall art, mirror, ottoman."
)


def analyze_room(
    image_bytes: bytes, media_type: str, style: str | None
) -> tuple[RoomAnalysis, bool, str | None]:
    """Analyse an uploaded room photo. ``style`` is the target style for the
    "New Room Design" flow; pass ``None`` for the "Modify Existing Room" flow,
    which has no target style — just a free-text instruction handled later by
    :func:`build_modify_prompt`."""
    if not settings.anthropic_ready:
        return _mock_analysis(style), True, None

    import base64

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    if style:
        instruction_text = (
            f"Analyse this room. The user wants to redesign it in a "
            f"{style} style, but describe what is ACTUALLY there now."
        )
    else:
        instruction_text = (
            "Analyse this already-furnished room and describe what is ACTUALLY "
            "there now — the user will separately describe what they want changed."
        )

    def _real() -> RoomAnalysis:
        resp = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=_MAX_TOKENS,
            system=ANALYSIS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {"type": "text", "text": instruction_text},
                    ],
                }
            ],
        )
        return RoomAnalysis(**_extract_json(_text_of(resp)))

    analysis, warning = run_or_degrade(
        _real, lambda: _mock_analysis(style), provider="anthropic", degrade_transient=True
    )
    return analysis, warning is not None, warning


# ===========================================================================
# 2. Adaptive follow-up questions
# ===========================================================================
QUESTIONS_SYSTEM = (
    "You are an interior designer preparing to redesign a room. Given the room "
    "analysis and target style, write 3-4 SHORT follow-up questions whose answers "
    "would most change your design. Rules:\n"
    "- The FIRST question must be about budget, in Indian Rupees, with exactly "
    "these three options: ₹10,000, ₹20,000, ₹30,000 (this is fixed and will be "
    "enforced regardless of what you write, so keep it simple).\n"
    "- Make the others SPECIFIC to this room: reference furniture that was "
    "detected by name, and the room's size and lighting. e.g. if a sofa was "
    "detected, ask whether to keep/replace/add seating; if the room reads small, "
    "ask about space priorities; if it reads dark, ask about lighting.\n"
    "- Give each question 3-5 concrete multiple-choice options.\n"
    "- The last question may be about colour and may be marked optional.\n"
    "Respond with ONLY a JSON array; each item:\n"
    '{"id": str (slug), "prompt": str, "kind": '
    '"budget"|"seating"|"space"|"storage"|"lighting"|"colors"|"priorities"|"other", '
    '"options": [str], "multi": bool, "optional": bool}'
)


def generate_questions(
    analysis: RoomAnalysis, style: str
) -> tuple[list[Question], bool, str | None]:
    if not settings.anthropic_ready:
        return _adaptive_questions(analysis, style), True, None

    def _real() -> list[Question]:
        resp = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=_MAX_TOKENS,
            system=QUESTIONS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Target style: {style}\n"
                        f"Room analysis JSON:\n{analysis.model_dump_json(indent=2)}"
                    ),
                }
            ],
        )
        data = _extract_json(_text_of(resp))
        questions = [Question(**q) for q in data]
        if not questions:
            raise ValueError("model returned no questions")
        # Always enforce our fixed ₹10k/₹20k/₹30k budget tiers, regardless of
        # what the model proposed for that question (or whether it asked one).
        non_budget = [q for q in questions if not (q.kind == "budget" or q.id == "budget")][:3]
        return [_budget_question()] + non_budget

    questions, warning = run_or_degrade(
        _real,
        lambda: _adaptive_questions(analysis, style),
        provider="anthropic",
        degrade_transient=True,
    )
    return questions, warning is not None, warning


# ===========================================================================
# 3. Build the text-to-image prompt + planned furniture list
# ===========================================================================
PROMPT_SYSTEM = (
    "You are an interior designer writing a single detailed prompt for an "
    "AI image generator (DALL-E) to render a photorealistic redesigned room. "
    "Combine the original room analysis, the target style, and the user's "
    "answers. Keep the room's architecture (windows, doors, proportions) but "
    "restyle furniture, textiles, colours and decor to fit the budget and "
    "priorities the user gave. If the answers include an 'additional_request', "
    "it is the user's own words about what to change — implement it literally "
    "and precisely. Respond with ONLY JSON:\n"
    "{\n"
    '  "image_prompt": str,  // one paragraph, <= 90 words, photorealistic, include camera framing\n'
    '  "planned_furniture": [{"name": str, "category": str, "description": str, "color": str}]\n'
    "     // 6-10 concrete pieces you are placing in the redesign\n"
    "}"
)


# Answer id used for the user's optional free-text change request (see
# routers/chat.py), so both the real and mock prompt builders can find it.
EXTRA_REQUEST_ID = "additional_request"


def build_image_prompt(
    analysis: RoomAnalysis, style: str, answers: list[dict[str, str]]
) -> tuple[str, list[FurnitureItem], bool, str | None]:
    if not settings.anthropic_ready:
        prompt, items = _mock_prompt(analysis, style, answers)
        return prompt, items, True, None

    answer_text = (
        "\n".join(f"- {a.get('question_id', a.get('id', '?'))}: {a['answer']}" for a in answers)
        or "- (none given)"
    )

    def _real() -> tuple[str, list[FurnitureItem]]:
        resp = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=_MAX_TOKENS,
            system=PROMPT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Target style: {style}\n\n"
                        f"Original room analysis JSON:\n{analysis.model_dump_json(indent=2)}\n\n"
                        f"User answers:\n{answer_text}"
                    ),
                }
            ],
        )
        data = _extract_json(_text_of(resp))
        prompt = str(data["image_prompt"]).strip()
        if not prompt:
            raise ValueError("empty image_prompt")
        items = [FurnitureItem(**it) for it in data.get("planned_furniture", [])]
        if not items:
            _, items = _mock_prompt(analysis, style, answers)
        return prompt, items

    (prompt, items), warning = run_or_degrade(
        _real,
        lambda: _mock_prompt(analysis, style, answers),
        provider="anthropic",
        degrade_transient=True,
    )
    return prompt, items, warning is not None, warning


# ===========================================================================
# 3b. "Modify Existing Room" flow — build the prompt from a free-text
#     instruction instead of a style + Q&A round trip.
# ===========================================================================
MODIFY_SYSTEM = (
    "You are an interior designer redesigning an ALREADY-FURNISHED room based on "
    "a homeowner's free-text instruction. You are given a JSON analysis of what "
    "is actually in the room now, plus their instruction, which may be GENERAL "
    "(e.g. 'make it more appealing', 'freshen it up') or SPECIFIC (e.g. 'move the "
    "table near the window to be near the bed instead', 'replace the sofa with "
    "something lighter'). Rules:\n"
    "- If the instruction is specific, implement it literally and precisely — "
    "do not ignore or water down any detail it names.\n"
    "- If the instruction is general, use good design judgement within the "
    "given budget, while keeping the room clearly recognisable as the same room.\n"
    "- Keep everything the instruction doesn't mention as close to the original "
    "as sensible (same architecture — windows, doors, proportions — and reuse "
    "existing furniture where it isn't being changed).\n"
    "Respond with ONLY JSON:\n"
    "{\n"
    '  "image_prompt": str,  // one paragraph, <= 90 words, photorealistic, include camera framing\n'
    '  "planned_furniture": [{"name": str, "category": str, "description": str, "color": str}]\n'
    "     // the FULL set of furniture/decor that should appear in the redesigned room —\n"
    "     // both pieces kept from the original and any changed/added/moved pieces\n"
    "}"
)


def build_modify_prompt(
    analysis: RoomAnalysis, instruction: str, budget: str | None
) -> tuple[str, list[FurnitureItem], bool, str | None]:
    if not settings.anthropic_ready:
        prompt, items = _mock_modify_prompt(analysis, instruction)
        return prompt, items, True, None

    def _real() -> tuple[str, list[FurnitureItem]]:
        resp = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=_MAX_TOKENS,
            system=MODIFY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Current room analysis JSON:\n{analysis.model_dump_json(indent=2)}\n\n"
                        f"User's instruction: {instruction}\n\n"
                        f"Budget for this refresh: {budget or '(not specified)'}"
                    ),
                }
            ],
        )
        data = _extract_json(_text_of(resp))
        prompt = str(data["image_prompt"]).strip()
        if not prompt:
            raise ValueError("empty image_prompt")
        items = [FurnitureItem(**it) for it in data.get("planned_furniture", [])]
        if not items:
            _, items = _mock_modify_prompt(analysis, instruction)
        return prompt, items

    (prompt, items), warning = run_or_degrade(
        _real,
        lambda: _mock_modify_prompt(analysis, instruction),
        provider="anthropic",
        degrade_transient=True,
    )
    return prompt, items, warning is not None, warning


# ===========================================================================
# Mock fallbacks
# ===========================================================================
def _mock_analysis(style: str) -> RoomAnalysis:
    return RoomAnalysis(
        room_type="living room",
        summary=(
            "A smallish living room that feels a bit tight and dim — a worn "
            "three-seat sofa, a dark wood coffee table, and not much storage. "
            "(Sample analysis — set ANTHROPIC_API_KEY in backend/.env for a real one.)"
        ),
        existing_furniture=[
            FurnitureItem(name="Three-seat sofa", category="sofa", description="Fabric, sagging cushions", color="brown"),
            FurnitureItem(name="Coffee table", category="coffee table", description="Scratched veneer", color="dark wood"),
            FurnitureItem(name="Floor lamp", category="floor lamp", description="Basic torchiere", color="black"),
            FurnitureItem(name="Area rug", category="rug", description="Small, sits off-centre", color="beige"),
            FurnitureItem(name="TV stand", category="console", description="Overcrowded, open shelves", color="black"),
        ],
        layout_notes="Sofa on the long wall, TV opposite; the walkway by the window is tight and the room reads small.",
        lighting="One north-facing window; mostly warm overhead light in the evening — on the dim side.",
        detected_colors=["brown", "beige", "off-white"],
    )


def _budget_question() -> Question:
    return Question(
        id="budget",
        prompt="What's your budget for this refresh?",
        kind="budget",
        options=list(VALID_BUDGETS),
    )


_SEATING_CATS = {"sofa", "couch", "sectional", "loveseat", "settee", "armchair", "bench"}


def _adaptive_questions(analysis: RoomAnalysis, style: str) -> list[Question]:
    """Pick budget + the 2-3 most relevant questions for what was detected."""
    text = " ".join(
        [analysis.summary, analysis.layout_notes, analysis.lighting]
        + [f"{f.name} {f.description}" for f in analysis.existing_furniture]
    ).lower()

    seating = [f for f in analysis.existing_furniture if f.category.lower() in _SEATING_CATS]
    small = any(k in text for k in ("small", "tight", "narrow", "cramped", "compact", "reads small", "limited space"))
    dark = any(k in text for k in ("dark", "dim", "limited natural", "north-facing", "low light", "little light", "no window"))
    cluttered = any(k in text for k in ("clutter", "crowded", "overcrowd", "messy", "no storage", "not much storage", "lacks storage"))
    colors = [c for c in analysis.detected_colors if c][:3]

    pool: list[Question] = []

    if seating:
        name = seating[0].name.lower()
        pool.append(Question(
            id="seating", kind="seating",
            prompt=f"You've got a {name} in there now — what should happen with the seating?",
            options=["Keep it and restyle around it", "Replace it with something new",
                     "Add another seat or two", "Not sure — you decide"],
        ))
    else:
        pool.append(Question(
            id="seating", kind="seating",
            prompt="There's no clear seating in the photo — what do you want?",
            options=["A sofa", "Sofa + an armchair", "A sectional", "Just a pair of chairs"],
        ))

    if small:
        pool.append(Question(
            id="space", kind="space",
            prompt="The room reads a little tight — what's the priority?",
            options=["Maximise open floor space", "Work in more storage",
                     "Still fit more seating", "Keep it airy and pared-back"],
        ))
    else:
        pool.append(Question(
            id="priorities", kind="priorities", multi=True,
            prompt="What matters most for the redesign? (pick up to two)",
            options=["More open space", "More storage", "More seating",
                     "Better lighting", "More display / decor"],
        ))

    if dark:
        pool.append(Question(
            id="lighting", kind="lighting",
            prompt="Lighting looks limited in here — how should we handle it?",
            options=["Layered lighting (lamps + overhead)", "Lighter colours to bounce light",
                     "One statement fixture", "Keep it warm and moody"],
        ))
    elif cluttered:
        pool.append(Question(
            id="storage", kind="storage",
            prompt="How much storage do you need?",
            options=["A lot — hide the clutter", "Some closed storage",
                     "Mostly open shelving", "Minimal — keep it sparse"],
        ))

    if colors:
        pool.append(Question(
            id="colors", kind="colors", optional=True,
            prompt=f"Your room's mostly {', '.join(colors)} right now — where do you want to take the palette?",
            options=["Keep a similar palette", "Warmer and cosier", "Cooler and calmer",
                     "Bolder, with strong accents", "Neutral and timeless"],
        ))
    else:
        pool.append(Question(
            id="colors", kind="colors", optional=True,
            prompt="Any colours you want to lean into or avoid?",
            options=["Warm neutrals", "Cool greys", "Earthy greens",
                     "Bold accents", "No preference"],
        ))

    # budget first, then contextual questions, de-duped by id, capped at 4.
    picked: list[Question] = [_budget_question()]
    seen = {"budget"}
    for q in pool:
        if q.id not in seen:
            picked.append(q)
            seen.add(q.id)
        if len(picked) == 4:
            break
    return picked


def _answers_map(answers: list[dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in answers:
        key = a.get("question_id") or a.get("id") or ""
        if key:
            out[key] = a.get("answer", "")
    return out


def _mock_prompt(
    analysis: RoomAnalysis, style: str, answers: list[dict[str, str]]
) -> tuple[str, list[FurnitureItem]]:
    palette = {
        "Modern": "warm oak, off-white walls, matte black accents, one terracotta note",
        "Minimalist": "white walls, pale wood, soft greys, a single muted accent",
        "Traditional": "rich walnut, deep burgundy and green, brass, warm ivory",
        "Scandinavian": "white walls, light beech, soft grey and blush textiles",
    }.get(style, "balanced neutral tones")

    amap = _answers_map(answers)
    extra = amap.pop(EXTRA_REQUEST_ID, "").strip()
    wants_storage = any("storage" in v.lower() for v in amap.values())
    wants_seating = any(("seat" in v.lower()) or ("sofa" in v.lower()) for v in amap.values())

    prompt = (
        f"Photorealistic interior photograph of a redesigned {analysis.room_type} in a {style} style, "
        f"same windows and proportions as the original, wide eye-level shot. A new low-profile sofa "
        f"anchors the seating over a large flat-weave rug, paired with a clean-lined coffee table, "
        f"an accent chair, a slim floor lamp and layered table lighting. "
        f"{'Generous closed storage plus open shelving keep it tidy. ' if wants_storage else 'Open shelving adds light storage. '}"
        f"{'An extra armchair expands the seating. ' if wants_seating else ''}"
        f"Framed art, a leafy plant and soft textiles finish it. Palette: {palette}. "
        f"{f'Also, as the homeowner asked: {extra}. ' if extra else ''}"
        f"Bright, tidy, magazine-quality daylight."
    )

    items = [
        FurnitureItem(name=f"{style} low-profile sofa", category="sofa", description="Three-seat, clean lines", color="neutral"),
        FurnitureItem(name="Accent armchair", category="armchair", description="Extra seating by the window", color="accent"),
        FurnitureItem(name="Coffee table", category="coffee table", description="Clean-lined, wood or stone top", color="wood"),
        FurnitureItem(name="Side table", category="side table", description="Next to the armchair", color="wood"),
        FurnitureItem(name="Large area rug", category="rug", description="Anchors the seating group", color="neutral"),
        FurnitureItem(name="Arc floor lamp", category="floor lamp", description="Reading light over the sofa", color="black"),
        FurnitureItem(name="Table lamp", category="table lamp", description="Warm ambient light", color="ceramic"),
        FurnitureItem(name="Media console", category="console", description="Closed storage for the TV wall", color="wood"),
        FurnitureItem(name="Open shelving unit", category="bookshelf", description="Display + light storage", color="wood"),
        FurnitureItem(name="Framed wall art", category="wall art", description="Set of two prints", color="neutral"),
        FurnitureItem(name="Floor plant", category="plant", description="Tall, in a woven basket", color="green"),
    ]
    return prompt, items


def _mock_modify_prompt(
    analysis: RoomAnalysis, instruction: str
) -> tuple[str, list[FurnitureItem]]:
    """Deterministic mock for the "Modify Existing Room" flow. Unlike the
    from-scratch mock above, this one is built directly around the user's own
    instruction text, so even without a live model the sample redesign
    visibly reflects what they actually asked for."""
    existing = analysis.existing_furniture or [
        FurnitureItem(name="Sofa", category="sofa", description="Existing seating", color="neutral"),
        FurnitureItem(name="Coffee table", category="coffee table", description="Existing table", color="wood"),
    ]
    kept_desc = ", ".join(f.name for f in existing[:5]) or "the existing furniture"
    instruction = instruction.strip()

    prompt = (
        f"Photorealistic interior photograph of the same {analysis.room_type}, same windows, "
        f"doors and proportions as the original — a targeted redesign, not a full replacement. "
        f'Apply this change exactly: "{instruction}". Keep {kept_desc} as they are except where '
        f"the instruction above says otherwise. Tidy styling, natural daylight, magazine-quality, "
        f"no text, no watermark, no people."
    )

    items = [
        FurnitureItem(
            name=f.name,
            category=f.category,
            description=(f"{f.description} — kept unless the instruction changes it").strip(" —"),
            color=f.color,
        )
        for f in existing
    ]
    items.append(
        FurnitureItem(
            name="Styling per your instruction",
            category="decor",
            description=(
                f'Reflects: "{instruction[:120]}" '
                "(Mock — set ANTHROPIC_API_KEY in backend/.env for a real one.)"
            ),
            color="",
        )
    )
    return prompt, items
