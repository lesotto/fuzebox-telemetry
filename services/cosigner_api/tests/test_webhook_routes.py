"""Webhook route smoke tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from services.cosigner_api.app import db
from services.cosigner_api.app.ledger import cosign as cosign_module
from services.cosigner_api.app.main import create_app
from services.cosigner_api.app.routes.webhooks import get_signer

STRIPE_SECRET = "whsec_test"


class _FakeSession:
    pass


async def _fake_get_session() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FUZEBOX_STRIPE_WEBHOOK_SECRET", STRIPE_SECRET)
    monkeypatch.setenv("FUZEBOX_STRIPE_TENANT", "acme")

    captured: dict[str, object] = {}

    async def fake_apply(*_a, **kw):  # type: ignore[no-untyped-def]
        captured.update(kw)
        # Return a fake row + event tuple.
        from types import SimpleNamespace

        row = SimpleNamespace(row_id=uuid.uuid4(), trust_level=3)
        event = SimpleNamespace(match_status="matched")
        return row, event

    monkeypatch.setattr(cosign_module, "apply_cosign", fake_apply)
    from services.cosigner_api.app.routes import webhooks as webhooks_routes

    monkeypatch.setattr(webhooks_routes, "apply_cosign", fake_apply)

    app = create_app()
    from services.cosigner_api.app.ledger.signing import StaticHMACProvider

    app.dependency_overrides[db.get_session] = _fake_get_session
    app.dependency_overrides[get_signer] = lambda: StaticHMACProvider(secret="webhook-test")
    return TestClient(app)


def _stripe_post(client: TestClient, body: dict, ts: int | None = None) -> object:
    raw = json.dumps(body).encode()
    ts = ts or int(time.time())
    sig = hmac.new(
        STRIPE_SECRET.encode(), f"{ts}.{raw.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return client.post(
        "/v1/webhooks/cosign/stripe",
        content=raw,
        headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"},
    )


def test_stripe_happy_path(client: TestClient) -> None:
    resp = _stripe_post(
        client,
        {
            "id": "evt_1",
            "data": {
                "object": {"object": "payment_intent", "id": "pi_1", "amount_received": 1000}
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "matched"
    assert body["trust_level"] == "3"


def test_stripe_bad_signature_rejected(client: TestClient) -> None:
    resp = client.post(
        "/v1/webhooks/cosign/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=ff"},
    )
    assert resp.status_code in {400, 401}


def test_unknown_adapter_404(client: TestClient) -> None:
    resp = client.post("/v1/webhooks/cosign/bogus", content=b"{}")
    assert resp.status_code == 404
