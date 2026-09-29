"""Build (or rebuild) the local product vector index used for semantic
recommendations, without starting the server.

    python scripts/build_product_index.py            # build if missing/stale
    python scripts/build_product_index.py --force     # always rebuild

Run from the backend/ folder so `app` is importable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import vector_store  # noqa: E402


def main() -> None:
    force = "--force" in sys.argv
    count = vector_store.ensure_index(force=force)
    print(f"Indexed {count} products using the '{vector_store.embedding_backend()}' embedding backend.")
    print(f"Persisted to: {vector_store.settings.chroma_dir}")


if __name__ == "__main__":
    main()
