"""SDK client: HTTP transport to the Cosigner API + local fallback buffer."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog

from .buffer import BufferedRow, LocalBuffer
from .exceptions import NotInitializedError

log = structlog.get_logger("fuzebox")

_DEFAULT_TIMEOUT = 2.0  # seconds; SDK must never block the agent for long


@dataclass
class _Config:
    api_key: str
    tenant: str
    endpoint: str
    timeout: float
    buffer_path: Path


_config: _Config | None = None
_buffer: LocalBuffer | None = None
_client: httpx.Client | None = None
_lock = threading.Lock()


def init(
    *,
    api_key: str,
    tenant: str,
    endpoint: str,
    timeout: float | None = None,
    buffer_path: str | os.PathLike[str] | None = None,
) -> None:
    """Initialize the SDK. Idempotent; calling twice with the same config is a no-op.

    Args:
        api_key: Tenant API key. Sent as `Authorization: Bearer ...`.
        tenant: Tenant slug. Sent as `X-Tenant-Id`.
        endpoint: Cosigner API base URL, e.g. ``https://fuzebox.acme.com``.
        timeout: Per-request timeout in seconds. Default 2s.
        buffer_path: Local SQLite path for the fail-open buffer.

    Example:
        >>> init(api_key="k", tenant="acme", endpoint="http://localhost:8080")
        >>> # safe to call again
        >>> init(api_key="k", tenant="acme", endpoint="http://localhost:8080")
    """

    global _config, _buffer, _client
    with _lock:
        new_cfg = _Config(
            api_key=api_key,
            tenant=tenant,
            endpoint=endpoint.rstrip("/"),
            timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
            buffer_path=Path(buffer_path) if buffer_path else _default_buffer_path(),
        )
        if _config is not None and _config == new_cfg:
            return
        if _client is not None:
            _client.close()
        if _buffer is not None:
            _buffer.close()
        _config = new_cfg
        _buffer = LocalBuffer(new_cfg.buffer_path)
        _client = httpx.Client(
            base_url=new_cfg.endpoint,
            timeout=new_cfg.timeout,
            headers={
                "Authorization": f"Bearer {new_cfg.api_key}",
                "X-Tenant-Id": new_cfg.tenant,
                "User-Agent": "fuzebox-python/0.1",
            },
        )
        log.info("fuzebox.init", tenant=new_cfg.tenant, endpoint=new_cfg.endpoint)
    # LiteLLM monkeypatch is installed outside the lock — it imports lazily and
    # must not deadlock with re-entrant init() calls in test fixtures.
    try:
        from . import litellm_wrapper

        litellm_wrapper.install()
    except Exception as exc:  # never raise from init
        log.warning("fuzebox.litellm.install.error", error=str(exc))


def shutdown() -> None:
    """Release HTTP client + buffer handles."""

    global _config, _client, _buffer
    with _lock:
        if _client is not None:
            _client.close()
            _client = None
        if _buffer is not None:
            _buffer.close()
            _buffer = None
        _config = None


def _default_buffer_path() -> Path:
    base = os.getenv("FUZEBOX_BUFFER_DIR")
    return Path(base) / "buffer.db" if base else Path.home() / ".fuzebox" / "buffer.db"


def _require_config() -> _Config:
    if _config is None:
        raise NotInitializedError("fuzebox.init must be called first")
    return _config


def _require_client() -> httpx.Client:
    if _client is None:
        raise NotInitializedError("fuzebox.init must be called first")
    return _client


def _require_buffer() -> LocalBuffer:
    if _buffer is None:
        raise NotInitializedError("fuzebox.init must be called first")
    return _buffer


def open_row(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /v1/pel/open. On failure, buffer locally and return a fail-open stub.

    The agent never sees this fail. If the network is down, the row is still
    given a `row_id`, but the response status is `unledgered` and the row is
    queued in the local buffer for reconciliation.
    """

    cfg = _require_config()
    client = _require_client()
    buffer = _require_buffer()

    try:
        resp = client.post("/v1/pel/open", json=payload)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("fuzebox.open.fail_open", error=str(exc))
        # Synthesize a local stub. The reconciliation worker will replay this.
        import uuid

        stub = {
            "row_id": str(uuid.uuid4()),
            "tenant_id": cfg.tenant,
            "agent_id": payload.get("agent_id"),
            "skill": payload.get("skill"),
            "case_id": payload.get("case_id"),
            "status": "unledgered",
            "trust_level": 0,
            "row_hash_hex": None,
            "signature_hex": None,
            "prev_hash_hex": None,
        }
        buffer.append(BufferedRow(row_id=stub["row_id"], tenant_id=cfg.tenant, payload=payload))
        return stub


def close_row(row_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST /v1/pel/{row_id}/close. Fail-open, returning None if buffered."""

    _require_config()
    client = _require_client()
    buffer = _require_buffer()

    try:
        resp = client.post(f"/v1/pel/{row_id}/close", json=payload)
        resp.raise_for_status()
        # On success, remove from buffer if it was queued.
        buffer.remove(row_id)
        return resp.json()  # type: ignore[no-any-return]
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("fuzebox.close.fail_open", row_id=row_id, error=str(exc))
        return None


__all__ = ["init", "shutdown", "open_row", "close_row"]
