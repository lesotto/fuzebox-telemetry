"""LiteLLM wrapper: cost accumulation while a row is open."""

from __future__ import annotations

import sys
import types
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

import fuzebox
from fuzebox import litellm_wrapper


@pytest.fixture
def fake_litellm(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Inject a stub `litellm` module before SDK init."""
    fake = types.ModuleType("litellm")

    def completion(*_a, **_kw):  # type: ignore[no-untyped-def]
        return {"_response_cost": 0.0009, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    fake.completion = completion
    monkeypatch.setitem(sys.modules, "litellm", fake)
    yield fake


def test_litellm_cost_recorded_on_row(fake_litellm, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    fuzebox.shutdown()
    # Re-install the wrapper since `litellm` is now stubbed.
    litellm_wrapper._installed = False
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://cosigner.test",
        buffer_path=tmp_path / "buf.db",
    )

    with respx.mock() as router:
        router.post("http://cosigner.test/v1/pel/open").mock(
            return_value=httpx.Response(
                201,
                json={
                    "row_id": "r1",
                    "tenant_id": "acme",
                    "agent_id": "a",
                    "skill": "s",
                    "case_id": "c",
                    "status": "open",
                    "trust_level": 1,
                    "row_hash_hex": "00",
                    "signature_hex": "00",
                    "prev_hash_hex": None,
                },
            )
        )
        captured: dict[str, object] = {}

        def _capture(req: httpx.Request) -> httpx.Response:
            captured["body"] = req.content.decode()
            return httpx.Response(200, json={"status": "closed"})

        router.post("http://cosigner.test/v1/pel/r1/close").mock(side_effect=_capture)

        with fuzebox.open_pel_row(skill="s", case_id="c") as _row:
            import litellm  # type: ignore[import-not-found]

            litellm.completion(model="x")

    assert "litellm_cost_usd" in captured["body"]
    body = captured["body"]
    assert "0.0009" in body  # cost dollars


def test_install_is_idempotent_without_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "litellm", None)
    litellm_wrapper._installed = False
    litellm_wrapper.install()  # must not raise
    litellm_wrapper.install()


def test_estimate_cost_from_usage_only() -> None:
    # If `_response_cost` is missing, we fall back to the conservative estimator.
    from fuzebox.litellm_wrapper import _estimate_cost

    assert _estimate_cost({"prompt_tokens": 1_000_000, "completion_tokens": 0}) == Decimal("1")
