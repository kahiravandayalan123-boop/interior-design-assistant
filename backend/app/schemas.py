"""Request/response models shared across the API."""
import re
from typing import Optional

from pydantic import BaseModel, Field

# Kept as a plain str set rather than a Literal so a novel style value from a
# client can be rejected explicitly in the router with a clear message instead
# of a 422 wall of Pydantic text.
Style = str
VALID_STYLES = ("Modern", "Minimalist", "Traditional", "Scandinavian")

# The three budget tiers offered on the budget question (new-room flow) and on
# the "Modify Existing Room" flow's own budget picker. Kept as one source of
# truth so the frontend, claude_service's mock question, and product_service's
# budget-fit scoring never drift apart.
VALID_BUDGETS = ("₹10,000", "₹20,000", "₹30,000")

# Currency markers stripped before reading the number: "₹", "Rs", "Rs."
# (any case) and thousands-separator commas.
_BUDGET_NOISE = re.compile(r"₹|\brs\.?|,", re.IGNORECASE)
_BUDGET_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def parse_budget_amount(budget: Optional[str]) -> Optional[float]:
    """Turn a budget label (e.g. "₹20,000", "Rs. 500", "15000") into a
    numeric INR ceiling, or ``None`` if unset/no number is present (callers
    should then skip budget filtering rather than silently treating it as
    zero). Single source of truth used by product_service and
    recommendation_service so a stated budget means the same total INR amount
    everywhere it's enforced."""
    if not budget:
        return None
    match = _BUDGET_NUMBER.search(_BUDGET_NOISE.sub("", budget))
    return float(match.group()) if match else None


BUDGET_TIGHT_MESSAGE = (
    "Budget is tight for a full room — here are the best matches within range."
)


class FurnitureItem(BaseModel):
    name: str = ""
    category: str = Field(default="", description="e.g. sofa, coffee table, rug, floor lamp")
    description: str = ""
    color: str = ""


class RoomAnalysis(BaseModel):
    room_type: str = "living room"
    summary: str = ""
    existing_furniture: list[FurnitureItem] = []
    layout_notes: str = ""
    lighting: str = ""
    detected_colors: list[str] = []


class Question(BaseModel):
    id: str
    prompt: str
    # free-form so a good question from Claude is never discarded over an
    # unexpected category label; the UI only special-cases "budget"/"priorities".
    kind: str = "other"
    options: list[str] = []
    multi: bool = False
    optional: bool = False


# ---- /api/upload ------------------------------------------------------------
class UploadResponse(BaseModel):
    session_id: str
    style: Style
    image_url: str
    analysis: RoomAnalysis
    questions: list[Question]
    mock: bool
    warnings: list[str] = []


# ---- /api/chat ------------------------------------------------------------
class ChatAnswer(BaseModel):
    question_id: str
    answer: str


class ChatRequest(BaseModel):
    session_id: str
    answers: list[ChatAnswer] = []
    message: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    questions: list[Question]
    answered: list["RecapItem"] = []
    ready_to_generate: bool
    mock: bool
    warnings: list[str] = []


# ---- /api/generate ------------------------------------------------------------
class GenerateRequest(BaseModel):
    session_id: str


class ProductMatch(BaseModel):
    item: str
    category: str
    product_id: str
    title: str
    brand: str
    price: float
    currency: str = "INR"
    retailer: str
    url: str
    image: str
    style_tags: list[str] = []
    match_score: float = 0.0


class ProductRecommendation(BaseModel):
    """A semantically-matched catalogue item, retrieved from the local Chroma
    vector store using the redesign's image prompt as the query — independent
    of (and in addition to) the rule-based ``ProductMatch`` list above."""
    product_id: str
    name: str
    category: str
    description: str = ""
    price: float
    currency: str = "INR"
    brand: str = ""
    retailer: str = ""
    url: str
    image: str = ""
    score: Optional[float] = None


class RecapItem(BaseModel):
    id: str
    kind: str = "other"
    question: str
    answer: str


class GenerateResponse(BaseModel):
    session_id: str
    style: Style
    image_prompt: str
    generated_image_url: str
    image_is_mock: bool
    planned_furniture: list[FurnitureItem]
    product_matches: list[ProductMatch]
    # Set when the stated budget couldn't fit every planned category — the
    # returned product_matches are still the best-fitting subset that DOES fit.
    product_matches_note: Optional[str] = None
    recommendations: list[ProductRecommendation] = []
    recommendations_total: float = 0.0
    recommendations_note: Optional[str] = None
    recap: list[RecapItem] = []
    estimated_total: float = 0.0
    mock: bool
    warnings: list[str] = []
    # Only populated by /api/modify (the "Modify Existing Room" flow), whose
    # session never goes through /api/upload — the "new" flow instead gets the
    # original photo URL from its earlier UploadResponse.
    original_image_url: str = ""


# ---- /api/products/match ------------------------------------------------------------
class ProductMatchRequest(BaseModel):
    items: list[FurnitureItem]
    style: Style = "Modern"
    budget: Optional[str] = None


class ProductMatchResponse(BaseModel):
    matches: list[ProductMatch]
    note: Optional[str] = None


ChatResponse.model_rebuild()
