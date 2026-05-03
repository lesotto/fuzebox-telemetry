"""Reconciliation worker.

Two responsibilities:

1. Surface PEL rows whose status is `unledgered` or `cosign_overdue` so
   operators can investigate.
2. Replay buffered rows from SDK clients that came online after a
   cosigner outage. (The SDK ships its buffer on reconnect; this worker
   drains the queue and posts each row to /v1/pel/open.)

Sprint 5 ships a Celery task surface plus the underlying drain functions.
The Celery app is constructed lazily so unit tests can exercise the drain
logic without a Redis dependency.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

log = structlog.get_logger("fuzebox.reconciliation")


@dataclass(frozen=True)
class ReconcileStats:
    queued: int
    posted: int
    failed: int


def _build_celery_app() -> Any:  # pragma: no cover — exercised in deploy
    from celery import Celery

    return Celery(
        "fuzebox.reconciliation",
        broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )


class PostOpenFn(Protocol):
    def __call__(self, payload: dict[str, Any]) -> None: ...


def drain_buffered(
    rows: Iterable[dict[str, Any]],
    *,
    post_open: PostOpenFn,
) -> ReconcileStats:
    """Drain a list of buffered rows, calling `post_open(payload)` for each.

    Returns counts. Pure function w.r.t. the iterable; no Celery required.
    """

    queued = 0
    posted = 0
    failed = 0
    for row in rows:
        queued += 1
        try:
            post_open(row)
            posted += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.warning("reconciliation.post.failed", error=str(exc))
    return ReconcileStats(queued=queued, posted=posted, failed=failed)


def register_tasks() -> Any:  # pragma: no cover — exercised in deploy
    """Register Celery tasks against the lazily-built app."""

    app = _build_celery_app()

    @app.task(name="reconciliation.drain_path")
    def drain_path(path: str) -> dict[str, int]:
        """Drain a JSON-lines file of buffered rows. Path must be local to the worker."""
        from os import unlink

        rows: list[dict[str, Any]] = []
        with open(path) as f:
            for line in f:
                rows.append(json.loads(line))
        # In production the worker forwards via httpx to the cosigner endpoint.
        import httpx

        client = httpx.Client(
            base_url=os.environ["FUZEBOX_COSIGNER_URL"],
            headers={
                "X-Tenant-Id": os.environ.get("FUZEBOX_DEFAULT_TENANT", "default"),
            },
            timeout=5,
        )

        def post_open(payload: dict[str, Any]) -> None:
            r = client.post("/v1/pel/open", json=payload)
            r.raise_for_status()

        stats = drain_buffered(rows, post_open=post_open)
        unlink(path)
        return {"queued": stats.queued, "posted": stats.posted, "failed": stats.failed}

    return app


__all__ = ["PostOpenFn", "ReconcileStats", "drain_buffered", "register_tasks"]
