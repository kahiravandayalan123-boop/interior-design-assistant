"""Product catalogue endpoints.

POST /api/products/match — match an explicit list of furniture items.
GET  /api/products        — dump the raw catalogue (handy for the frontend / debugging).
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from ..config import get_settings
from ..schemas import ProductMatchRequest, ProductMatchResponse
from ..services.product_service import match_products

router = APIRouter(prefix="/api/products", tags=["products"])
settings = get_settings()


@router.get("")
async def list_products():
    with open(settings.products_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/match", response_model=ProductMatchResponse)
async def products_match(req: ProductMatchRequest):
    matches, note = match_products(req.items, style=req.style, budget=req.budget)
    return ProductMatchResponse(matches=matches, note=note)
