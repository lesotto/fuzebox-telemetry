"""Public `open_pel_row` context manager.

This is the only object a customer agent ever interacts with. It must:

- Never raise from happy-path failures (network, signature errors).
- Auto-attach to the current OTEL trace context if one exists.
- Allow `set_predicted_outcome_usd`, `set_actual_outcome_usd`, `add_meta`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import structlog

from . import client, litellm_wrapper

log = structlog.get_logger("fuzebox")


class PELRow:
    """Proxy returned by `open_pel_row`.

    Mutations are buffered locally and flushed on context exit.

    Example:
        >>> # row = PELRow(...); row.set_predicted_outcome_usd(Decimal("1.50"))
        >>> # row.add_meta(key="value")
    """

    def __init__(
        self,
        *,
        row_id: str,
        tenant_id: str,
        agent_id: str,
        skill: str,
        case_id: str,
        status: str,
        trust_level: int,
    ) -> None:
        self.row_id = row_id
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.skill = skill
        self.case_id = case_id
        self.status = status
        self.trust_level = trust_level
        self._predicted_outcome_usd: Decimal | None = None
        self._actual_outcome_usd: Decimal | None = None
        self._extra_meta: dict[str, Any] = {}

    def set_predicted_outcome_usd(self, value: Decimal | float | int) -> None:
        self._predicted_outcome_usd = Decimal(str(value))

    def set_actual_outcome_usd(self, value: Decimal | float | int) -> None:
        self._actual_outcome_usd = Decimal(str(value))

    def add_meta(self, **kwargs: Any) -> None:
        self._extra_meta.update(kwargs)

    def _close_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"extra_meta": self._extra_meta}
        if self._predicted_outcome_usd is not None:
            payload["predicted_outcome_usd"] = str(self._predicted_outcome_usd)
        if self._actual_outcome_usd is not None:
            payload["actual_outcome_usd"] = str(self._actual_outcome_usd)
        return payload


@contextmanager
def open_pel_row(
    *,
    skill: str,
    case_id: str | None = None,
    agent_id: str = "default",
    model: str | None = None,
    cost_usd: Decimal | float | int = 0,
    meta: dict[str, Any] | None = None,
) -> Iterator[PELRow]:
    """Open a hash-chained, signed PEL row for the duration of the `with` block.

    Args:
        skill: Logical name of the work being done (e.g. ``"claims_triage"``).
        case_id: Business identifier (e.g. claim id). Auto-generated if absent.
        agent_id: Identifier for the executing agent.
        model: Optional model name (e.g. ``"gpt-4o-mini"``).
        cost_usd: Optional fixed cost; auto-instrumentation adds LLM call costs in Sprint 2.
        meta: Free-form metadata. Stripe / Salesforce match keys go here.

    Yields:
        A `PELRow` proxy; mutate before exiting the `with` block.

    Example:
        >>> # with open_pel_row(skill="claims_triage") as row:
        >>> #     row.set_predicted_outcome_usd(50)
    """

    case_id = case_id or str(uuid.uuid4())
    payload = {
        "agent_id": agent_id,
        "skill": skill,
        "case_id": case_id,
        "model": model,
        "cost_usd": str(Decimal(str(cost_usd))),
        "meta": meta or {},
    }

    started = time.perf_counter()
    try:
        opened = client.open_row(payload)
    except Exception as exc:  # ultimate safety net — never block the agent
        log.error("fuzebox.open_pel_row.unexpected", error=str(exc))
        opened = {
            "row_id": str(uuid.uuid4()),
            "tenant_id": "unknown",
            "agent_id": agent_id,
            "skill": skill,
            "case_id": case_id,
            "status": "unledgered",
            "trust_level": 0,
        }

    row = PELRow(
        row_id=opened["row_id"],
        tenant_id=opened.get("tenant_id", "unknown"),
        agent_id=opened.get("agent_id", agent_id),
        skill=opened.get("skill", skill),
        case_id=opened.get("case_id", case_id),
        status=opened.get("status", "open"),
        trust_level=int(opened.get("trust_level", 0)),
    )

    token = litellm_wrapper.set_active_row(row)  # noqa: F841
    try:
        yield row
    finally:
        # Add LiteLLM-recorded cost into the row payload if any.
        litellm_cost = getattr(row, "_litellm_cost", None)
        if litellm_cost is not None:
            row.add_meta(litellm_cost_usd=str(litellm_cost))
        litellm_wrapper.set_active_row(None)
        try:
            client.close_row(row.row_id, row._close_payload())
        except Exception as exc:  # ultimate safety net
            log.error("fuzebox.close.unexpected", row_id=row.row_id, error=str(exc))
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "fuzebox.row.complete",
            row_id=row.row_id,
            skill=row.skill,
            case_id=row.case_id,
            elapsed_ms=round(elapsed_ms, 3),
        )


__all__ = ["PELRow", "open_pel_row"]
