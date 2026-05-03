"""LiteLLM auto-instrumentation.

Monkeypatches `litellm.completion` and `litellm.acompletion` so every call
made inside an `open_pel_row` block contributes to the row's `cost_usd` and
adds a span entry. Customers never import this module directly — `init`
installs it.
"""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import structlog

log = structlog.get_logger("fuzebox.litellm")

_installed = False
_install_lock = threading.Lock()

# Per-row accumulator so concurrent contexts don't bleed into one another.
_active_row: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "fuzebox_active_row", default=None
)


def set_active_row(row: Any | None) -> None:
    """Bind a PELRow to the current async/thread context."""

    _active_row.set(row)


def install() -> None:
    """Install the LiteLLM monkeypatch. Idempotent and safe-no-op if LiteLLM is absent."""

    global _installed
    with _install_lock:
        if _installed:
            return
        try:
            import litellm  # type: ignore[import-not-found]
        except ImportError:
            log.info("fuzebox.litellm.not_installed")
            return

        _wrap_sync(litellm)
        _wrap_async(litellm)
        _installed = True
        log.info("fuzebox.litellm.installed")


def _record(response: Any) -> None:
    row = _active_row.get()
    if row is None:
        return
    try:
        cost = response.get("_response_cost") if isinstance(response, dict) else getattr(
            response, "_response_cost", None
        )
        if cost is None:
            usage = (
                response.get("usage")
                if isinstance(response, dict)
                else getattr(response, "usage", None)
            )
            if usage is None:
                return
            cost = _estimate_cost(usage)
        if cost is None:
            return
        existing = getattr(row, "_litellm_cost", Decimal("0"))
        row._litellm_cost = existing + Decimal(str(cost))
    except Exception as exc:  # never propagate from instrumentation
        log.warning("fuzebox.litellm.record.error", error=str(exc))


def _estimate_cost(usage: Any) -> Decimal | None:
    try:
        prompt = int(
            usage.get("prompt_tokens", 0) if isinstance(usage, dict) else usage.prompt_tokens
        )
        completion = int(
            usage.get("completion_tokens", 0)
            if isinstance(usage, dict)
            else usage.completion_tokens
        )
    except (AttributeError, ValueError):
        return None
    # Conservative fallback: $1 per 1M tokens. Real cost comes from LiteLLM's
    # `_response_cost` when the customer has model pricing configured.
    return Decimal(prompt + completion) / Decimal(1_000_000)


def _wrap_sync(litellm: Any) -> None:
    original = litellm.completion

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        _record(result)
        return result

    litellm.completion = wrapped


def _wrap_async(litellm: Any) -> None:
    original = getattr(litellm, "acompletion", None)
    if original is None:
        return

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        _record(result)
        return result

    litellm.acompletion = wrapped


__all__ = ["install", "set_active_row"]


_ = Callable  # keep type alias import even when unused
