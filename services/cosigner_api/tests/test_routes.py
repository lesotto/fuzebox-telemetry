"""Route-level smoke tests with stubbed DB and signer.

Exercises request/response shapes for /v1/pel/open and /v1/pel/{row_id}/close.
Real DB integration lives in `test_repo_postgres.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.cosigner_api.app import db
from services.cosigner_api.app.ledger import repo
from services.cosigner_api.app.ledger.signing import StaticHMACProvider
from services.cosigner_api.app.main import create_app
from services.cosigner_api.app.routes.pel import get_signer


class _FakeSession:
    """Minimal stand-in. The route layer only invokes the repo functions."""


async def _fake_get_session() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _make_row(row_id: uuid.UUID | None = None, *, status: str = "open") -> SimpleNamespace:
    return SimpleNamespace(
        row_id=row_id or uuid.uuid4(),
        tenant_id="acme",
        agent_id="a",
        skill="claims_triage",
        case_id="c1",
        status=status,
        trust_level=1,
        row_hash=b"\x01" * 32,
        signature=b"\x02" * 32,
        prev_hash=None,
        created_at=datetime(2026, 5, 3, tzinfo=UTC),
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_app()
    app.dependency_overrides[db.get_session] = _fake_get_session
    app.dependency_overrides[get_signer] = lambda: StaticHMACProvider(secret="route-test")

    async def fake_open(_session, _req, _signer):  # type: ignore[no-untyped-def]
        return _make_row()

    async def fake_close(_session, req, _signer):  # type: ignore[no-untyped-def]
        return _make_row(row_id=req.row_id, status="closed")

    monkeypatch.setattr(repo, "open_row", fake_open)
    monkeypatch.setattr(repo, "close_row", fake_close)
    # Routes import the symbols at module load time.
    from services.cosigner_api.app.routes import pel as pel_routes

    monkeypatch.setattr(pel_routes, "open_row", fake_open)
    monkeypatch.setattr(pel_routes, "close_row", fake_close)
    return TestClient(app)


def test_open_row_route(client: TestClient) -> None:
    resp = client.post(
        "/v1/pel/open",
        headers={"X-Tenant-Id": "acme"},
        json={
            "agent_id": "a",
            "skill": "claims_triage",
            "case_id": "c1",
            "cost_usd": "0.001",
            "meta": {"stripe_payment_intent_id": "pi_x"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["trust_level"] == 1
    assert len(body["row_hash_hex"]) == 64


def test_close_row_route(client: TestClient) -> None:
    row_id = str(uuid.uuid4())
    resp = client.post(
        f"/v1/pel/{row_id}/close",
        headers={"X-Tenant-Id": "acme"},
        json={"predicted_outcome_usd": "12.50", "extra_meta": {"k": "v"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "closed"
    assert body["row_id"] == row_id


def test_open_row_missing_tenant_header(client: TestClient) -> None:
    resp = client.post("/v1/pel/open", json={"agent_id": "a", "skill": "s", "case_id": "c"})
    assert resp.status_code == 422


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
