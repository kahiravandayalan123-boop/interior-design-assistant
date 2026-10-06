"""OpenAI image generation (DALL·E) with an offline-safe mock.

`generate_image()` always returns raw PNG bytes plus metadata; the caller
persists them and serves them from our own origin (so the before/after slider
and the "Download image" button work without CORS or expiring URLs).

Readiness:
* No OPENAI_API_KEY (or FORCE_MOCK) -> a locally synthesized placeholder PNG.
* Real key + the user's room photo -> OpenAI `images.edit`, so the render is
  built *on* their photo (same camera angle, walls, windows, doors, stairs)
  instead of imagining a new room from text alone.
* Real key, no photo available -> `images.generate` (text-to-image).
  Both are on the `gpt-image-1` family, which always returns inline base64
  data (no `response_format` param, and no second request to an expiring CDN
  URL).

The moment a valid OPENAI_API_KEY is added to backend/.env and the backend is
restarted, the real path runs with no code change. Transient failures
(rate-limit, timeout, network, 5xx) raise ServiceError so the UI can offer a
retry; permanent ones (bad key, no credit, content policy) fall back to the
placeholder plus a warning so the flow still completes.

Note: `dall-e-3`/`dall-e-2` were retired from the OpenAI API; this targets the
current `gpt-image-1` model family (also covers `gpt-image-1-mini`,
`gpt-image-1.5`, `gpt-image-2`, ...), which has a different parameter set
(`quality` is low/medium/high/auto, `size` is 1024x1024/1024x1536/1536x1024/
auto, and there is no `style` param or `response_format` param).
"""
from __future__ import annotations

import base64
import math
import struct
import zlib
from dataclasses import dataclass

from ..config import get_settings
from .errors import ServiceError, classify_provider_error

settings = get_settings()
_client = None

_MAX_PROMPT_CHARS = 3800
_VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}

# Wall / floor / accent RGB per style, used by the placeholder renderer.
_PALETTE = {
    "Modern": ((236, 231, 221), (197, 177, 143), (206, 120, 72)),
    "Minimalist": ((247, 245, 240), (214, 206, 187), (169, 180, 160)),
    "Traditional": ((233, 221, 196), (99, 66, 38), (124, 43, 43)),
    "Scandinavian": ((251, 250, 246), (222, 196, 154), (217, 167, 91)),
}


@dataclass
class ImageResult:
    data: bytes
    content_type: str
    mock: bool
    warning: str | None = None


# ---------------------------------------------------------------------------
def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        # No automatic retry: a second full-length attempt would double the
        # wait before the user sees "took too long" — the UI offers a retry.
        _client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_image_timeout,
            max_retries=0,
        )
    return _client


def build_dalle_prompt(raw: str, style: str, room_type: str = "room") -> str:
    """Clean and frame the model-written prompt for a text-to-image API."""
    text = " ".join((raw or "").split())
    # Drop any leftover mock/parenthetical notes so the real API never sees them.
    for marker in ("(Mock", "(mock", "add OPENAI", "add ANTHROPIC"):
        idx = text.find(marker)
        if idx != -1:
            end = text.find(")", idx)
            text = (text[:idx] + (text[end + 1 :] if end != -1 else "")).strip()
    if not text:
        text = f"A tastefully redesigned {room_type} in a {style} interior-design style."
    framed = (
        f"{text} Interior-design photograph, realistic proportions and materials, "
        f"natural daylight, styled and uncluttered, no text, no watermark, no people."
    )
    return framed[:_MAX_PROMPT_CHARS]


# Prepended when editing the user's own photo: the model-written prompt
# describes the new furnishings, this pins down what must NOT change.
_EDIT_PREFIX = (
    "Redesign the room in this exact photo. Keep the same camera angle, framing "
    "and perspective, and keep the architecture unchanged: walls, ceiling, "
    "windows, doors, any stairs, floor plan and room proportions must stay "
    "exactly where they are. Change only the furniture, decor, textiles, lighting fixtures, "
    "colours and finishes as described: "
)


def generate_image(
    prompt: str,
    style: str,
    room_type: str = "room",
    source_image: bytes | None = None,
    source_media_type: str = "image/jpeg",
) -> ImageResult:
    """Render the redesign. Pass the user's photo as `source_image` so the
    output is an edit of their actual room rather than a new invented one."""
    if not settings.openai_ready:
        return ImageResult(_placeholder_png(style), "image/png", mock=True)

    try:
        if source_image:
            framed = build_dalle_prompt(_EDIT_PREFIX + (prompt or ""), style, room_type)
            return _edit_real(framed, source_image, source_media_type)
        return _generate_real(build_dalle_prompt(prompt, style, room_type))
    except ServiceError:
        raise
    except Exception as exc:  # noqa: BLE001 - classified below
        se = classify_provider_error(exc, provider="openai")
        if se.degrade:
            return ImageResult(
                _placeholder_png(style), "image/png", mock=True, warning=se.user_message
            )
        raise se


def _generate_real(framed_prompt: str) -> ImageResult:
    size = settings.openai_image_size if settings.openai_image_size in _VALID_SIZES else "1024x1024"
    kwargs = dict(
        model=settings.openai_image_model,
        prompt=framed_prompt,
        size=size,
        n=1,
    )
    # gpt-image-1 (and siblings) always return b64_json inline with no
    # response_format param; quality is low/medium/high/auto, no "style" param.
    if settings.openai_image_model.startswith("gpt-image"):
        kwargs["quality"] = settings.openai_image_quality

    return _extract_image(_get_client().images.generate(**kwargs))


def _edit_real(framed_prompt: str, source: bytes, media_type: str) -> ImageResult:
    ext = {"image/png": "png", "image/webp": "webp"}.get(media_type, "jpg")
    kwargs = dict(
        model=settings.openai_image_model,
        image=(f"room.{ext}", source, media_type),
        prompt=framed_prompt,
        # "auto" lets the API match the photo's aspect ratio (landscape rooms
        # stay landscape) instead of squashing everything to a square.
        size=settings.openai_edit_size if settings.openai_edit_size in _VALID_SIZES else "auto",
        n=1,
    )
    if settings.openai_image_model.startswith("gpt-image"):
        kwargs["quality"] = settings.openai_image_quality
        # High fidelity keeps the original layout and details much closer.
        # Not every model in the family accepts it (e.g. the -mini variants).
        if settings.openai_input_fidelity and "mini" not in settings.openai_image_model:
            kwargs["input_fidelity"] = settings.openai_input_fidelity

    return _extract_image(_get_client().images.edit(**kwargs))


def _extract_image(resp) -> ImageResult:
    if not getattr(resp, "data", None):
        raise ServiceError(
            "The image service returned an empty response. Please try again.",
            status_code=502, retryable=True, kind="empty",
        )
    item = resp.data[0]

    b64 = getattr(item, "b64_json", None)
    if b64:
        return ImageResult(base64.b64decode(b64), "image/png", mock=False)

    url = getattr(item, "url", None)
    if url:  # defensive: some models/settings return a URL instead
        import httpx2 as httpx

        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "image/png").split(";")[0].strip()
        return ImageResult(r.content, ctype or "image/png", mock=False)

    raise ServiceError(
        "The image service response had no image data. Please try again.",
        status_code=502, retryable=True, kind="empty",
    )


# ---------------------------------------------------------------------------
# Offline placeholder: a stdlib-only PNG so mock mode needs no network and the
# download button has real bytes to hand back today.
# ---------------------------------------------------------------------------
def _png(width: int, height: int, rows: list[bytearray]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter: none
        raw.extend(row)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def _lerp(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _placeholder_png(style: str, width: int = 768, height: int = 576) -> bytes:
    wall, floor, accent = _PALETTE.get(style, _PALETTE["Modern"])
    wall_top = _lerp(wall, (255, 255, 255), 0.25)
    floor_dark = _lerp(floor, (0, 0, 0), 0.18)
    sofa = _lerp(floor, (90, 90, 95), 0.5) if style != "Traditional" else _lerp(accent, (0, 0, 0), 0.2)

    fy = int(height * 0.66)
    win_x0, win_x1 = int(width * 0.56), int(width * 0.9)
    win_y0, win_y1 = int(height * 0.12), int(height * 0.56)
    glow_cx, glow_cy, glow_r = width * 0.73, height * 0.28, height * 0.55
    rug_cx, rug_cy, rug_rx, rug_ry = width * 0.42, height * 0.82, width * 0.34, height * 0.13
    sofa_x0, sofa_x1 = int(width * 0.08), int(width * 0.52)
    sofa_y0, sofa_y1 = int(height * 0.44), fy + int(height * 0.02)

    rows: list[bytearray] = []
    for y in range(height):
        row = bytearray(width * 3)
        on_floor = y >= fy
        base_floor_t = (y - fy) / max(height - fy, 1) if on_floor else 0.0
        wall_t = y / max(fy, 1)
        for x in range(width):
            if on_floor:
                r, g, b = _lerp(floor, floor_dark, base_floor_t)
                dx = (x - rug_cx) / rug_rx
                dy = (y - rug_cy) / rug_ry
                if dx * dx + dy * dy <= 1.0:
                    r, g, b = _lerp((r, g, b), accent, 0.34)
            else:
                r, g, b = _lerp(wall_top, wall, wall_t)
                if win_x0 <= x <= win_x1 and win_y0 <= y <= win_y1:
                    r, g, b = _lerp((r, g, b), (231, 239, 241), 0.7)

            # warm light glow (both planes)
            d = math.hypot(x - glow_cx, y - glow_cy) / glow_r
            if d < 1.0:
                r, g, b = _lerp((r, g, b), (255, 240, 205), 0.22 * (1.0 - d))

            # simple sofa block
            if sofa_x0 <= x <= sofa_x1 and sofa_y0 <= y <= sofa_y1:
                r, g, b = _lerp((r, g, b), sofa, 0.82)

            i = x * 3
            row[i] = max(0, min(255, r))
            row[i + 1] = max(0, min(255, g))
            row[i + 2] = max(0, min(255, b))
        rows.append(row)

    return _png(width, height, rows)
