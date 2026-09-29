"""Shared room-photo validation for /api/upload and /api/modify.

Content-Type from the browser is advisory only; the magic-byte sniff below is
the source of truth for what actually got uploaded.
"""
from __future__ import annotations

MAX_BYTES = 10 * 1024 * 1024
MIN_BYTES = 100

# magic-byte signatures -> canonical (media_type, extension).
_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"RIFF", "image/webp", ".webp"),  # + "WEBP" at offset 8, checked below
)


def sniff(data: bytes) -> tuple[str, str] | None:
    for sig, media, ext in _SIGNATURES:
        if data.startswith(sig):
            if media == "image/webp" and data[8:12] != b"WEBP":
                continue
            return media, ext
    return None
