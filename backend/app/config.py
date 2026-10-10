"""Application configuration, loaded from backend/.env.

Nothing here raises if a key is missing. `openrouter_ready` / `openai_ready`
tell the services whether a real API call is possible; when they're False the
services return mock data so the whole flow stays testable before keys exist.

Uses only python-dotenv + stdlib so there's no extra dependency to install.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


# Origins that may always call this API (see Settings.cors_origin_list).
ALWAYS_ALLOWED_ORIGINS = (
    "https://interior-design-assistant-omega.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()

    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5").strip()
    openai_image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
    openai_image_size: str = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip()
    openai_image_quality: str = os.getenv("OPENAI_IMAGE_QUALITY", "high").strip()
    # Used when redesigning the user's own photo (images.edit). "auto" keeps
    # the photo's aspect ratio; input fidelity "high" preserves its layout.
    openai_edit_size: str = os.getenv("OPENAI_EDIT_SIZE", "auto").strip()
    openai_input_fidelity: str = os.getenv("OPENAI_INPUT_FIDELITY", "high").strip()

    # Per-request timeouts (seconds). The SDK defaults are 10 minutes with 2
    # retries — far too long for a live demo, where a stuck call should fail
    # fast and show the user a message instead.
    anthropic_timeout: float = float(os.getenv("ANTHROPIC_TIMEOUT", "90"))
    openai_image_timeout: float = float(os.getenv("OPENAI_IMAGE_TIMEOUT", "150"))

    cors_origins: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    # Optional regex for origins that can't be listed ahead of time, e.g.
    # Vercel's per-deploy preview URLs: https://.*\.vercel\.app
    cors_origin_regex: str = os.getenv("CORS_ORIGIN_REGEX", "").strip()
    force_mock: bool = _env_bool("FORCE_MOCK", False)
    # Compare each render against the original photo's architecture and
    # re-render once if a window / door / staircase was added or removed.
    verify_structure: bool = _env_bool("VERIFY_STRUCTURE", True)

    # --- derived helpers -------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        # The production frontend is always allowed, whatever CORS_ORIGINS says:
        # a missing dashboard variable must not be able to take the live site
        # down (every browser call then fails as "can't reach the server").
        origins = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        for o in ALWAYS_ALLOWED_ORIGINS:
            if o not in origins:
                origins.append(o)
        return origins

    @property
    def anthropic_ready(self) -> bool:
        return bool(self.anthropic_api_key) and not self.force_mock

    @property
    def openai_ready(self) -> bool:
        return bool(self.openai_api_key) and not self.force_mock

    @property
    def upload_dir(self) -> Path:
        p = BACKEND_DIR / "app" / "storage" / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def generated_dir(self) -> Path:
        p = BACKEND_DIR / "app" / "storage" / "generated"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def products_file(self) -> Path:
        return BACKEND_DIR / "app" / "data" / "products.json"

    # --- semantic product recommendations (Chroma vector store) ----------
    @property
    def data_dir(self) -> Path:
        p = BACKEND_DIR / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def recommendations_products_file(self) -> Path:
        return self.data_dir / "products.json"

    @property
    def chroma_dir(self) -> Path:
        p = self.data_dir / "chroma_db"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
