"""Normalise an uploaded room photo before anything else sees it.

The image model can only output three canvas shapes (square, 3:2 landscape,
2:3 portrait). If the photo is any other shape — and phone photos are 4:3 or
16:9 — the model has to invent the missing strip of room, which is where
staircases, extra doorways and "rooms that don't exist" come from. So the
photo is cropped to the nearest supported shape *first*, and that cropped
frame is what gets analysed, shown as "Before", and edited into "After":
all three are the same frame, pixel for pixel.

Also applies the EXIF rotation (phones store portrait shots sideways) and
caps the size, which keeps multi-megabyte uploads from slowing every step.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

# (width, height) canvases the image model supports.
CANVASES = ((1024, 1024), (1536, 1024), (1024, 1536))

# A panorama or a sliver would lose most of the room to the crop.
_MAX_ASPECT = 2.4


class PhotoError(ValueError):
    """The file isn't a usable room photo; the message is safe to show."""


@dataclass
class PreparedPhoto:
    data: bytes  # JPEG bytes, exactly width x height
    media_type: str  # always image/jpeg
    width: int
    height: int

    @property
    def size(self) -> str:
        return f"{self.width}x{self.height}"


def prepare_photo(raw: bytes) -> PreparedPhoto:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PhotoError(
            "That image couldn't be opened — it may be corrupt. Please choose a different photo."
        ) from exc

    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        # Flatten transparency onto white rather than black.
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            img = background
        else:
            img = img.convert("RGB")

    w, h = img.size
    if min(w, h) < 256:
        raise PhotoError(
            "That photo is too small to work with. Please use one at least 256 pixels on each side."
        )
    aspect = w / h
    if aspect > _MAX_ASPECT or aspect < 1 / _MAX_ASPECT:
        raise PhotoError(
            "That photo is too wide or too tall (panoramas don't work). "
            "Please use a normal landscape or portrait photo of the room."
        )

    target_w, target_h = min(CANVASES, key=lambda c: abs((c[0] / c[1]) - aspect))
    # Centre-crop to the canvas shape, then resize to exactly the canvas.
    img = ImageOps.fit(img, (target_w, target_h), method=Image.LANCZOS, centering=(0.5, 0.5))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return PreparedPhoto(out.getvalue(), "image/jpeg", target_w, target_h)


def size_of(data: bytes) -> str | None:
    """`WxH` of stored image bytes, or None if they can't be read."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            return f"{img.width}x{img.height}"
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def downscale_jpeg(data: bytes, max_side: int = 1024) -> bytes:
    """Smaller JPEG copy for vision checks (faster, cheaper, same content)."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()
