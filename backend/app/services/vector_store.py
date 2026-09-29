"""Local, persisted semantic product index (Chroma) used for AI-recommended
products — separate from and additional to product_service's rule-based
category/style/budget matching.

Embeddings come from OpenAI's ``text-embedding-3-small`` when an API key is
configured (``settings.openai_ready``), otherwise from a local
sentence-transformers model (``all-MiniLM-L6-v2``) so retrieval still works
completely offline. The two embedding spaces aren't comparable, so each one
gets its own Chroma collection — switching backends (e.g. adding a key later)
just builds the other collection rather than mixing incompatible vectors.

The index is built once and persisted under backend/data/chroma_db; on
startup/first query it's rebuilt only if the catalogue file's item count
doesn't match what's already indexed, so a normal restart doesn't re-embed.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

logger = logging.getLogger("interior_design_assistant.vector_store")
settings = get_settings()

OPENAI_EMBED_MODEL = "text-embedding-3-small"
LOCAL_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_BASE = "products"
_BATCH = 64

_local_model = None  # lazily loaded sentence-transformers model


def embedding_backend() -> str:
    return "openai" if settings.openai_ready else "local"


def _collection_name() -> str:
    # Namespaced by backend so switching embedding sources never mixes
    # incompatible vector spaces in one collection.
    return f"{COLLECTION_BASE}_{embedding_backend()}"


def _load_products() -> list[dict]:
    path = settings.recommendations_products_file
    if not path.is_file():
        raise FileNotFoundError(
            f"Product catalogue not found at {path}. Run "
            "scripts/build_product_index.py after adding backend/data/products.json."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=1)
    resp = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _embed_local(texts: list[str]) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        _local_model = SentenceTransformer(LOCAL_EMBED_MODEL)
    return _local_model.encode(list(texts), normalize_embeddings=True).tolist()


def embed(texts: list[str]) -> list[list[float]]:
    return _embed_openai(texts) if embedding_backend() == "openai" else _embed_local(texts)


@lru_cache
def _client():
    import chromadb

    return chromadb.PersistentClient(path=str(settings.chroma_dir))


def _get_collection():
    return _client().get_or_create_collection(
        _collection_name(), metadata={"hnsw:space": "cosine"}
    )


def ensure_index(force: bool = False) -> int:
    """Build the Chroma collection if it's missing or out of sync with the
    catalogue file. Returns the number of indexed items. Safe to call on
    every startup/query — it's a no-op once the index is current."""
    products = _load_products()
    coll = _get_collection()

    if not force and coll.count() == len(products):
        return coll.count()

    if coll.count():
        _client().delete_collection(_collection_name())
        coll = _get_collection()

    ids = [p["product_id"] for p in products]
    docs = [f"{p['name']}. {p['category']}. {p.get('description', '')}" for p in products]
    metadatas = [
        {
            "name": p["name"],
            "category": p["category"],
            "description": p.get("description", ""),
            "price": float(p["price"]),
            "currency": p.get("currency", "INR"),
            "brand": p.get("brand", ""),
            "retailer": p.get("retailer", ""),
            "url": p["url"],
            "image": p.get("image", ""),
        }
        for p in products
    ]

    for i in range(0, len(ids), _BATCH):
        chunk_docs = docs[i : i + _BATCH]
        coll.add(
            ids=ids[i : i + _BATCH],
            documents=chunk_docs,
            embeddings=embed(chunk_docs),
            metadatas=metadatas[i : i + _BATCH],
        )

    logger.info(
        "Built product vector index: %d items via the %s embedding backend.",
        len(ids), embedding_backend(),
    )
    return len(ids)


def query(text: str, top_k: int = 6) -> list[dict]:
    """Embed ``text`` and return up to ``top_k`` nearest catalogue items as
    plain dicts (product metadata + a 0-1 ``score``, higher is closer),
    already sorted by relevance descending."""
    ensure_index()
    coll = _get_collection()
    [query_embedding] = embed([text])
    res = coll.query(query_embeddings=[query_embedding], n_results=top_k)

    ids = res["ids"][0] if res["ids"] else []
    metadatas = res["metadatas"][0] if res["metadatas"] else []
    distances = res["distances"][0] if res["distances"] else []

    out = []
    for product_id, meta, distance in zip(ids, metadatas, distances):
        # cosine distance in [0, 2]; convert to a friendlier 0-1 similarity score.
        score = max(0.0, min(1.0, 1.0 - distance / 2.0))
        out.append({"product_id": product_id, **meta, "score": round(score, 4)})
    return out


def all_products() -> list[dict]:
    """The full catalogue, in the same dict shape ``query()`` returns
    (``score`` is ``None`` since these weren't ranked by relevance) — used to
    broaden a budget-constrained search when nothing relevant fits."""
    return [
        {
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p["category"],
            "description": p.get("description", ""),
            "price": float(p["price"]),
            "currency": p.get("currency", "INR"),
            "brand": p.get("brand", ""),
            "retailer": p.get("retailer", ""),
            "url": p["url"],
            "image": p.get("image", ""),
            "score": None,
        }
        for p in _load_products()
    ]
