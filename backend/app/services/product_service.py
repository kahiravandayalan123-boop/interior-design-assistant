"""Match furniture items against the local product catalogue.

Pure Python, no external calls. Per detected item:
  1. normalise its category (synonyms, then a broad-term fallback);
  2. gather candidates in that category (with a fuzzy contains-match backstop);
  3. score by style-tag match, colour overlap and budget fit;
  4. return the best not-yet-used product (falls back to the top pick if the
     category is exhausted).
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from ..config import get_settings
from ..schemas import BUDGET_TIGHT_MESSAGE, FurnitureItem, ProductMatch, parse_budget_amount

settings = get_settings()
logger = logging.getLogger("interior_design_assistant.products")

# exact-phrase synonyms -> canonical catalogue category
_CATEGORY_SYNONYMS = {
    "couch": "sofa", "sectional": "sofa", "loveseat": "sofa", "settee": "sofa",
    "sofa bed": "sofa", "3-seat sofa": "sofa", "two-seat sofa": "sofa",
    "centre table": "coffee table", "center table": "coffee table",
    "cocktail table": "coffee table", "coffee/cocktail table": "coffee table",
    "carpet": "rug", "area rug": "rug", "floor rug": "rug",
    "lamp": "floor lamp", "standing lamp": "floor lamp", "torchiere": "floor lamp",
    "reading lamp": "floor lamp", "arc lamp": "floor lamp",
    "desk lamp": "table lamp", "bedside lamp": "table lamp", "accent lamp": "table lamp",
    "accent chair": "armchair", "lounge chair": "armchair", "wingback": "armchair",
    "wing chair": "armchair", "recliner": "armchair", "club chair": "armchair",
    "occasional chair": "armchair", "reading chair": "armchair", "easy chair": "armchair",
    "dining chairs": "dining chair", "kitchen chair": "dining chair", "side chair": "dining chair",
    "dining set": "dining table", "kitchen table": "dining table", "dinner table": "dining table",
    "bookcase": "bookshelf", "shelving": "bookshelf", "shelf": "bookshelf",
    "shelves": "bookshelf", "open shelving": "bookshelf", "shelving unit": "bookshelf",
    "etagere": "bookshelf", "wall shelf": "bookshelf",
    "media console": "console", "tv stand": "console", "tv unit": "console",
    "media unit": "console", "media cabinet": "console", "entertainment center": "console",
    "media bench": "console", "tv console": "console",
    "credenza": "sideboard", "buffet": "sideboard", "cabinet": "sideboard",
    "storage cabinet": "sideboard", "dresser": "sideboard",
    "end table": "side table", "nightstand": "side table", "bedside table": "side table",
    "nesting table": "side table", "accent table": "side table", "drinks table": "side table",
    "drapes": "curtains", "drapery": "curtains", "window treatment": "curtains",
    "window treatments": "curtains", "blinds": "curtains", "sheers": "curtains",
    "artwork": "wall art", "art": "wall art", "painting": "wall art", "print": "wall art",
    "prints": "wall art", "framed print": "wall art", "wall decor": "wall art",
    "gallery wall": "wall art", "poster": "wall art",
    "wall mirror": "mirror", "floor mirror": "mirror", "leaner mirror": "mirror",
    "pouf": "ottoman", "footstool": "ottoman", "foot stool": "ottoman",
    "storage ottoman": "ottoman", "hassock": "ottoman",
    "houseplant": "plant", "potted plant": "plant", "indoor plant": "plant",
    "fiddle leaf fig": "plant", "snake plant": "plant", "greenery": "plant",
    "throw": "textiles", "throw blanket": "textiles", "blanket": "textiles",
    "cushions": "textiles", "pillows": "textiles", "throw pillows": "textiles",
    "window bench": "bench", "entry bench": "bench", "storage bench": "bench",
}

# broad word in the (already-normalised) category -> canonical fallback
_BROAD_FALLBACK = [
    ("dining table", "dining table"), ("dining chair", "dining chair"),
    ("table lamp", "table lamp"), ("floor lamp", "floor lamp"),
    ("coffee", "coffee table"), ("side", "side table"), ("console", "console"),
    ("sideboard", "sideboard"), ("shelf", "bookshelf"), ("shelv", "bookshelf"),
    ("book", "bookshelf"), ("storage", "bookshelf"), ("cabinet", "sideboard"),
    ("chair", "armchair"), ("sofa", "sofa"), ("seat", "sofa"), ("couch", "sofa"),
    ("lamp", "floor lamp"), ("light", "floor lamp"), ("rug", "rug"),
    ("carpet", "rug"), ("table", "coffee table"), ("mirror", "mirror"),
    ("art", "wall art"), ("print", "wall art"), ("wall", "wall art"),
    ("plant", "plant"), ("curtain", "curtains"), ("drape", "curtains"),
    ("ottoman", "ottoman"), ("pouf", "ottoman"), ("stool", "ottoman"),
    ("bench", "bench"), ("throw", "textiles"), ("pillow", "textiles"),
    ("cushion", "textiles"),
]

@lru_cache
def _catalogue() -> list[dict]:
    with open(settings.products_file, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def _canonical_categories() -> frozenset[str]:
    return frozenset(p["category"] for p in _catalogue())


def _normalize_category(raw: str) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return ""
    # Already an exact catalogue category (e.g. "table lamp", "side table") —
    # resolve it as-is BEFORE trying substring synonyms, or a generic synonym
    # like "lamp" -> "floor lamp" would wrongly rewrite "table lamp".
    if key in _canonical_categories():
        return key
    if key in _CATEGORY_SYNONYMS:
        return _CATEGORY_SYNONYMS[key]
    for phrase, canon in _CATEGORY_SYNONYMS.items():
        if phrase in key:
            return canon
    return key


def _resolve_category(item: FurnitureItem) -> str:
    for raw in (item.category, item.name):
        cat = _normalize_category(raw)
        if not cat:
            continue
        if cat in _canonical_categories():
            return cat
        for word, canon in _BROAD_FALLBACK:
            if word in cat:
                return canon
    return _normalize_category(item.category) or _normalize_category(item.name)


def _candidates(cat: str) -> list[dict]:
    exact = [p for p in _catalogue() if p["category"] == cat]
    if exact:
        return exact
    # fuzzy: catalogue category shares a word with the requested one
    words = set(cat.split())
    return [p for p in _catalogue() if words & set(p["category"].split())]


def _relevance_score(product: dict, item: FurnitureItem, style: str) -> float:
    """Pure style/colour fit — independent of price. Budget is enforced
    separately as a hard cap on the *combined* selection (see
    match_products), not folded into this score, so a well-matched but
    expensive item can no longer out-rank affordability considerations."""
    score = 1.0  # category already matched by the caller
    tags = product.get("style_tags", [])
    if style in tags:
        score += 2.5
    elif tags:
        score += 0.2  # still style-compatible, just not the primary style
    item_color = (item.color or "").lower()
    if item_color and any(item_color in c or c in item_color for c in product.get("colors", [])):
        score += 1.0
    return round(score, 3)


def _best_pick(item: FurnitureItem, cat: str, candidates: list[dict], style: str, seen: set[str]) -> tuple[dict, float] | None:
    # Ties on relevance go to the cheaper product, leaving more budget headroom.
    ranked = sorted(candidates, key=lambda p: (-_relevance_score(p, item, style), float(p["price"])))
    pick = next((p for p in ranked if p["product_id"] not in seen), None)
    if pick is None:
        return None
    return pick, _relevance_score(pick, item, style)


def _to_match(item: FurnitureItem, cat: str, product: dict, score: float) -> ProductMatch:
    return ProductMatch(
        item=item.name or product["title"],
        category=cat,
        product_id=product["product_id"],
        title=product["title"],
        brand=product["brand"],
        price=float(product["price"]),
        currency=product.get("currency", "INR"),
        retailer=product["retailer"],
        url=product["url"],
        image=product["image"],
        style_tags=product.get("style_tags", []),
        match_score=score,
    )


def match_products(
    items: list[FurnitureItem], style: str = "Modern", budget: str | None = None
) -> tuple[list[ProductMatch], str | None]:
    """Rank-then-fit: for each planned item, find its single best style/colour
    match per category (as before), then — if a budget was given — greedily
    keep matches in relevance order while the running total stays within it,
    skipping (not swapping in a cheaper alternative for) any match that would
    push the total over. If nothing in that primary pass fits at all, fall
    back to the cheapest available items overall so the shopper still sees
    *something* affordable, with a note explaining why the list is thin.

    Returns ``(matches, note)`` — ``note`` is ``None`` unless the budget
    actually caused items to be dropped or the fallback path was used.
    """
    budget_amount = parse_budget_amount(budget)
    logger.debug("match_products: budget=%r -> budget_amount=%r, %d items", budget, budget_amount, len(items))

    seen: set[str] = set()
    picks: list[tuple[FurnitureItem, str, dict, float]] = []
    for item in items:
        cat = _resolve_category(item)
        candidates = _candidates(cat)
        if not candidates:
            continue
        found = _best_pick(item, cat, candidates, style, seen)
        if found is None:
            continue
        product, score = found
        seen.add(product["product_id"])
        picks.append((item, cat, product, score))

    if budget_amount is None:
        logger.debug("match_products: no budget cap -> returning all %d picks unfiltered", len(picks))
        return [_to_match(item, cat, p, score) for item, cat, p, score in picks], None

    # Greedy fit in relevance order — highest-scoring matches get first claim
    # on the budget; a lower-relevance but cheaper item can still fit in
    # afterwards if an expensive higher-relevance one was skipped. Ties on
    # relevance go cheapest-first so more items fit.
    picks_by_relevance = sorted(picks, key=lambda t: (-t[3], float(t[2]["price"])))
    selected: list[tuple[FurnitureItem, str, dict, float]] = []
    running_total = 0.0
    any_skipped = False
    for entry in picks_by_relevance:
        price = float(entry[2]["price"])
        if running_total + price <= budget_amount:
            selected.append(entry)
            running_total += price
            logger.debug("  keep %s ₹%.0f -> running_total=₹%.0f", entry[2]["product_id"], price, running_total)
        else:
            any_skipped = True
            logger.debug("  skip %s ₹%.0f (would be ₹%.0f > ₹%.0f)", entry[2]["product_id"], price, running_total + price, budget_amount)

    note = None
    if not selected:
        logger.debug("match_products: nothing fit -> cheapest-item fallback")
        # Nothing even in the best-matched pool fits — broaden to the
        # cheapest catalogue items overall (any category) so the shopper
        # still sees affordable options instead of an empty list.
        all_products = sorted(_catalogue(), key=lambda p: p["price"])
        fallback_seen: set[str] = set()
        for product in all_products:
            if product["product_id"] in fallback_seen:
                continue
            price = float(product["price"])
            if running_total + price <= budget_amount:
                fallback_seen.add(product["product_id"])
                running_total += price
                selected.append((
                    FurnitureItem(name=product["title"], category=product["category"]),
                    product["category"], product, 0.0,
                ))
        if not selected and all_products:
            # Even the single cheapest catalogue item exceeds the budget —
            # best effort: show it anyway rather than an empty shopping list.
            cheapest = all_products[0]
            running_total = float(cheapest["price"])
            selected = [(
                FurnitureItem(name=cheapest["title"], category=cheapest["category"]),
                cheapest["category"], cheapest, 0.0,
            )]
        note = BUDGET_TIGHT_MESSAGE
    elif any_skipped:
        note = BUDGET_TIGHT_MESSAGE

    matches = [_to_match(item, cat, p, score) for item, cat, p, score in selected]
    logger.debug("match_products: result %d items, total=₹%.0f, note=%r", len(matches), running_total, note)
    return matches, note
