"""Semantic product recommendations for the redesign response.

Takes the same image prompt used for DALL-E generation and retrieves the
nearest catalogue items from the local Chroma vector store (see
vector_store.py), then — if a budget was given — greedily keeps the
highest-relevance items whose combined price stays within it, the same
rank-then-fit approach as product_service.match_products. Deliberately never
raises on a lookup failure: a broken embedding call, a corrupt/missing index,
or a missing catalogue file just logs and returns an empty list, so a
recommendations outage never breaks /generate or /modify — the same
"degrade, don't dead-end" spirit as image_service's mock fallback.
"""
from __future__ import annotations

import logging

from ..schemas import BUDGET_TIGHT_MESSAGE, ProductRecommendation, parse_budget_amount
from . import vector_store
from .shop_links import shop_links

logger = logging.getLogger("interior_design_assistant.recommendations")

DEFAULT_TOP_K = 6
# How many relevance-ranked candidates to pull before applying the budget
# filter, so a greedy pass has real room to find a combination that fits.
POOL_SIZE = 24


# Floor-hungry categories that shouldn't be suggested as extras for a small room.
_LARGE = ("sofa", "armchair", "dining table", "dining chair", "sideboard", "bookshelf", "console", "bench", "coffee table")


def _excluded(category: str, exclude: set[str], small_room: bool) -> bool:
    cat = (category or "").lower()
    if small_room and any(big in cat for big in _LARGE):
        return True
    return any(e and (e in cat or cat in e) for e in exclude)


def _to_recommendation(hit: dict) -> ProductRecommendation:
    links = shop_links(hit.get("name", ""), "", hit.get("category", ""))
    return ProductRecommendation(
        product_id=hit["product_id"],
        name=hit.get("name", ""),
        category=hit.get("category", ""),
        description=hit.get("description", ""),
        price=float(hit.get("price", 0.0)),
        currency=hit.get("currency", "INR"),
        brand=hit.get("brand", ""),
        retailer=hit.get("retailer", ""),
        url=links[0].url,
        shop_links=links,
        image=hit.get("image", ""),
        score=hit.get("score"),
    )


def get_recommendations(
    query_text: str, budget: str | None = None, top_k: int = DEFAULT_TOP_K,
    exclude_categories: set[str] | None = None, small_room: bool = False,
) -> tuple[list[ProductRecommendation], str | None]:
    """Returns ``(recommendations, note)``. ``note`` is ``None`` unless the
    budget caused items to be dropped or a fallback to cheaper items ran."""
    text = (query_text or "").strip()
    if not text:
        return [], None

    budget_amount = parse_budget_amount(budget)
    logger.debug("get_recommendations: budget=%r -> budget_amount=%r, top_k=%d", budget, budget_amount, top_k)

    try:
        hits = vector_store.query(text, top_k=POOL_SIZE)
    except Exception:
        logger.exception("Product recommendation lookup failed; omitting recommendations.")
        return [], None
    # Extras only: nothing in a category the plan already keeps, removes or
    # buys, and nothing bulky for a small room.
    exclude = {c.lower() for c in (exclude_categories or set())}
    hits = [h for h in hits if not _excluded(h.get("category", ""), exclude, small_room)]

    if budget_amount is None:
        logger.debug("get_recommendations: no budget cap -> returning top %d of %d hits unfiltered", top_k, len(hits))
        return _safe_build(hits[:top_k]), None

    # Re-sort by relevance (similarity) descending, breaking ties cheapest-first
    # so tied items favour fitting more into the budget.
    hits = sorted(hits, key=lambda h: (-(h.get("score") or 0.0), float(h.get("price", 0.0))))
    selected: list[dict] = []
    running_total = 0.0
    any_skipped = False
    for hit in hits:
        if len(selected) >= top_k:
            break
        price = float(hit.get("price", 0.0))
        if running_total + price <= budget_amount:
            selected.append(hit)
            running_total += price
            logger.debug("  keep %s ₹%.0f -> running_total=₹%.0f", hit.get("product_id"), price, running_total)
        else:
            any_skipped = True
            logger.debug("  skip %s ₹%.0f (would be ₹%.0f > ₹%.0f)", hit.get("product_id"), price, running_total + price, budget_amount)

    note = BUDGET_TIGHT_MESSAGE if (any_skipped and selected) else None

    logger.debug("get_recommendations: result %d items, total=₹%.0f, note=%r",
                 len(selected), sum(float(h.get("price", 0.0)) for h in selected), note)
    return _safe_build(selected), note


def _safe_build(hits: list[dict]) -> list[ProductRecommendation]:
    recommendations = []
    for hit in hits:
        try:
            recommendations.append(_to_recommendation(hit))
        except Exception:
            logger.exception("Skipping malformed recommendation hit: %r", hit)
    return recommendations
