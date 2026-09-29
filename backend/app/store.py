"""In-memory session store.

Scaffold-grade: state lives in a process dict, so it resets on reload and
won't work across multiple workers. Swap for Redis / a database later — every
consumer goes through get_session()/save_session() so the change is localized.
"""
import threading
import time
import uuid
from typing import Any, Optional

_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}


def new_session(data: dict[str, Any]) -> str:
    session_id = uuid.uuid4().hex
    with _LOCK:
        _SESSIONS[session_id] = {"id": session_id, "created_at": time.time(), **data}
    return session_id


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        session = _SESSIONS.get(session_id)
        return dict(session) if session else None


def update_session(session_id: str, patch: dict[str, Any]) -> Optional[dict[str, Any]]:
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None:
            return None
        session.update(patch)
        return dict(session)
