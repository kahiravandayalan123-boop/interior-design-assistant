"""FastAPI entrypoint for the AI Interior Design Assistant.

Run from the backend/ folder:
    venv\\Scripts\\uvicorn app.main:app --reload      (Windows)
    uvicorn app.main:app --reload                     (macOS/Linux)

Interactive docs at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import chat, generate, modify, products, session, upload

# Uvicorn only configures its own loggers; without this the app's INFO lines
# (request timings, startup, provider failures) never reach the Railway logs.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("interior_design_assistant")
settings = get_settings()

STARTED_AT = time.time()
VERSION = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "dev")[:7]

app = FastAPI(
    title="AI Interior Design Assistant API",
    version="0.1.0",
    description="Upload a room photo, pick a style, answer a few questions, get a redesign + shopping list.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# One line per API call with its outcome and duration, so a slow or failing
# request can be found in the logs afterwards.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("%s %s crashed after %.1fs", request.method, request.url.path, time.perf_counter() - start)
        raise
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        took = time.perf_counter() - start
        log = logger.warning if response.status_code >= 500 else logger.info
        log("%s %s -> %d in %.1fs", request.method, request.url.path, response.status_code, took)
    return response


# Any exception that isn't already an HTTPException is a bug — log it and
# return a plain-JSON 500 instead of an HTML traceback, so the frontend's
# jsonOrThrow() always has something readable to show the user.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Please try again."},
    )


def _serve_local_file(directory, filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Bad filename.")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(404, "Not found.")
    return FileResponse(path)


_CATEGORY_THUMBS_DIR = Path(__file__).resolve().parent / "storage" / "category_thumbnails"
app.mount("/media/categories", StaticFiles(directory=_CATEGORY_THUMBS_DIR), name="category_thumbnails")


@app.get("/media/uploads/{filename}", name="serve_upload", include_in_schema=False)
async def serve_upload(filename: str):
    return _serve_local_file(settings.upload_dir, filename)


@app.get("/media/generated/{filename}", name="serve_generated", include_in_schema=False)
async def serve_generated(filename: str):
    return _serve_local_file(settings.generated_dir, filename)


@app.get("/health", tags=["meta"])
async def health():
    # uptime resets whenever the process restarts — and a restart wipes the
    # in-memory sessions, so this makes "did the server restart?" answerable.
    return {"status": "ok", "version": VERSION, "uptime_seconds": int(time.time() - STARTED_AT)}


@app.get("/api/config", tags=["meta"])
async def config():
    """Lets the frontend show a banner when it's running on mock data, and
    tells it exactly which provider is still on mock."""
    return {
        "anthropic_ready": settings.anthropic_ready,
        "openai_ready": settings.openai_ready,
        "using_mock": not (settings.anthropic_ready and settings.openai_ready),
        "anthropic_model": settings.anthropic_model,
        "openai_image_model": settings.openai_image_model,
        "version": VERSION,
        "verify_structure": settings.verify_structure,
        "timeouts": {"anthropic": settings.anthropic_timeout, "openai_image": settings.openai_image_timeout},
    }


def _build_index() -> None:
    try:
        from .services import vector_store

        count = vector_store.ensure_index()
        logger.info(
            "Product recommendation index ready: %d items (%s embeddings).",
            count, vector_store.embedding_backend(),
        )
    except Exception:
        logger.exception(
            "Could not build the product vector index at startup; "
            "recommendations will be omitted until this succeeds."
        )


@app.on_event("startup")
async def _startup() -> None:
    """Build the semantic product index in the background: it calls an
    external embeddings API, and a slow reply there must never hold up the
    server coming online."""
    logger.info("Starting version %s; CORS origins: %s", VERSION, settings.cors_origin_list)
    threading.Thread(target=_build_index, name="product-index", daemon=True).start()


app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(generate.router)
app.include_router(modify.router)
app.include_router(products.router)
app.include_router(session.router)
