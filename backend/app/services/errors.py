"""Provider-error handling shared by the Claude and OpenAI services.

Two outcomes for a failed provider call:

* **degrade** — the failure won't fix itself on retry (bad key, no credit,
  content policy, malformed response, unknown model). The caller falls back to
  mock output and surfaces `warning` so the UI can show a soft notice. The demo
  keeps moving.
* **raise** — a transient failure (rate limit, timeout, network, 5xx). The
  router turns it into an HTTP error with a friendly message and the UI offers
  a retry.

`run_or_degrade()` wraps a real call + its mock fallback and applies the policy.
"""
from __future__ import annotations

import json
import re
from typing import Callable, TypeVar

from pydantic import ValidationError

T = TypeVar("T")

_ENV_VAR = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_LABEL = {"anthropic": "the design service", "openai": "the image service"}

_CREDIT_RE = re.compile(
    r"credit balance|insufficient|exceeded your current quota|billing|"
    r"payment required|out of credit|too low to",
    re.I,
)
_POLICY_RE = re.compile(
    r"content policy|content_policy|safety system|flagged|rejected as a result",
    re.I,
)


class ServiceError(Exception):
    """A provider failure already translated into something safe to show a user."""

    def __init__(
        self,
        user_message: str,
        *,
        status_code: int = 502,
        retryable: bool = False,
        degrade: bool = False,
        kind: str = "error",
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.retryable = retryable
        self.degrade = degrade
        self.kind = kind


def _short(msg: str, limit: int = 160) -> str:
    msg = " ".join((msg or "").split())
    return msg if len(msg) <= limit else msg[: limit - 1] + "…"


def classify_provider_error(exc: Exception, *, provider: str) -> ServiceError:
    """Map an SDK/HTTP exception to a ServiceError with a user-facing message."""
    name = type(exc).__name__
    msg = _short(str(getattr(exc, "message", "") or exc))
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    label = _LABEL.get(provider, "an external service")
    env_var = _ENV_VAR.get(provider, "the API key")

    # ---- permanent: fall back to a sample and warn -------------------------
    if name == "AuthenticationError" or status == 401:
        return ServiceError(
            f"{label.capitalize()} rejected the API key — check {env_var} in backend/.env.",
            degrade=True, kind="auth",
        )
    if name == "PermissionDeniedError" or status == 403:
        return ServiceError(
            f"The API key for {label} doesn't have access to the requested model.",
            degrade=True, kind="auth",
        )
    if _CREDIT_RE.search(msg):
        return ServiceError(
            f"{label.capitalize()} account has run out of credit. Add funds to the "
            f"{provider.capitalize()} account and try again.",
            degrade=True, kind="credit",
        )
    if provider == "openai" and _POLICY_RE.search(msg):
        return ServiceError(
            "The image provider blocked this request under its content policy. "
            "Try another room photo or a different style.",
            degrade=True, kind="policy",
        )
    if name == "NotFoundError" or status == 404:
        return ServiceError(
            f"The model configured for {label} wasn't found — check the model name in backend/.env.",
            degrade=True, kind="model",
        )
    if name in ("BadRequestError", "UnprocessableEntityError") or status in (400, 422):
        return ServiceError(
            f"{label.capitalize()} rejected the request ({msg or 'bad request'}).",
            degrade=True, kind="bad_request",
        )

    # ---- transient: block with a retry ----------------------------------
    if name == "RateLimitError" or status == 429:
        return ServiceError(
            f"{label.capitalize()} is rate-limited right now. Wait a few seconds and try again.",
            status_code=429, retryable=True, kind="rate_limit",
        )
    if name == "APITimeoutError" or "timed out" in msg.lower() or "timeout" in msg.lower():
        return ServiceError(
            f"{label.capitalize()} took too long to respond. Please try again.",
            status_code=504, retryable=True, kind="timeout",
        )
    if name == "APIConnectionError" or "connection error" in msg.lower():
        return ServiceError(
            f"Couldn't reach {label}. Check your internet connection and try again.",
            status_code=503, retryable=True, kind="network",
        )
    if isinstance(status, int) and status >= 500:
        return ServiceError(
            f"{label.capitalize()} had a server error. Please try again in a moment.",
            status_code=502, retryable=True, kind="upstream",
        )

    # ---- unknown -----------------------------------------------------
    return ServiceError(
        f"Unexpected problem talking to {label} ({msg or name}).",
        status_code=502, retryable=True, kind="unknown",
    )


def run_or_degrade(
    real_fn: Callable[[], T],
    mock_fn: Callable[[], T],
    *,
    provider: str,
    degrade_transient: bool = False,
) -> tuple[T, str | None]:
    """Run ``real_fn``; on failure either fall back to ``mock_fn`` (returning a
    warning string) or re-raise as a ServiceError.

    ``degrade_transient=True`` makes even rate-limit/network errors fall back to
    the mock instead of raising — use it for steps that must never dead-end.
    """
    try:
        return real_fn(), None
    except ServiceError:
        raise
    except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as exc:
        return mock_fn(), (
            f"{provider.capitalize()} returned an unexpected response, so a sample "
            f"was used for this step. ({_short(str(exc), 120)})"
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad; classify below
        se = classify_provider_error(exc, provider=provider)
        if se.degrade or (degrade_transient and se.retryable):
            return mock_fn(), se.user_message
        raise se
