"""Real, working shopping links.

The bundled catalogue is a demo dataset (invented brands, estimated prices),
so there is no real product page to deep-link to. Instead every piece links
to a live search for that kind of item on real Indian retailers, built from
what the design actually calls for (e.g. "arc floor lamp matte black").
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from ..schemas import ShopLink

_RETAILERS = (
    ("Amazon", "https://www.amazon.in/s?k={q}"),
    ("Flipkart", "https://www.flipkart.com/search?q={q}"),
    ("IKEA", "https://www.ikea.com/in/en/search/?q={q}"),
)

_NOISE = re.compile(r"\(.*?\)|[^\w\s-]", re.UNICODE)
_STOP = {"kept", "new", "existing", "the", "a", "an", "and", "with", "for", "in", "of", "set"}


def search_query(name: str, color: str = "", category: str = "") -> str:
    """Short keyword query: the item name, plus its colour if not already in it."""
    words = [w for w in _NOISE.sub(" ", name or category or "").lower().split() if w not in _STOP]
    colour = [w for w in _NOISE.sub(" ", (color or "").split("/")[0].split(",")[0]).lower().split() if w not in _STOP]
    for w in colour[:2]:
        if w not in words:
            words.append(w)
    if category and not any(c in words for c in category.lower().split()):
        words.extend(category.lower().split())
    return " ".join(words[:7]) or "home decor"


def shop_links(name: str, color: str = "", category: str = "") -> list[ShopLink]:
    q = quote_plus(search_query(name, color, category))
    return [ShopLink(retailer=r, url=tpl.format(q=q)) for r, tpl in _RETAILERS]
