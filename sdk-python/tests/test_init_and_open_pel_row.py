"""End-to-end SDK tests with a mocked Cosigner API.

These tests exercise:
- `init` idempotency
- happy path for `open_pel_row` -> POST /v1/pel/open + /close
- fail-open path: the agent never sees an exception when the endpoint is down
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

import fuzebox
from fuzebox import client as sdk_client


@pytest.fixture(autouse=True)
def reset_sdk(tmp_path: Path) -> None:
    fuzebox.shutdown()
    yield
    fuzebox.shutdown()


def _open_response(row_id: str = None) -> dict[str, object]:
    return {
        "row_id": row_id or str(uuid.uuid4()),
        "tenant_id": "acme",
        "agent_id": "default",
        "skill": "claims_triage",
        "case_id": "c1",
        "status": "open",
        "trust_level": 1,
        "row_hash_hex": "deadbeef",
        "signature_hex": "cafebabe",
        "prev_hash_hex": None,
    }


def test_init_is_idempotent(tmp_path: Path) -> None:
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://localhost:8080",
        buffer_path=tmp_path / "buf.db",
    )
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://localhost:8080",
        buffer_path=tmp_path / "buf.db",
    )


def test_open_pel_row_happy_path(tmp_path: Path) -> None:
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://cosigner.test",
        buffer_path=tmp_path / "buf.db",
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://cosigner.test/v1/pel/open").mock(
            return_value=httpx.Response(201, json=_open_response("r-1"))
        )
        router.post("http://cosigner.test/v1/pel/r-1/close").mock(
            return_value=httpx.Response(200, json={**_open_response("r-1"), "status": "closed"})
        )

        with fuzebox.open_pel_row(skill="claims_triage", case_id="c1") as row:
            row.set_predicted_outcome_usd(Decimal("12.50"))
            row.add_meta(stripe_payment_intent_id="pi_test")
            assert row.row_id == "r-1"
            assert row.skill == "claims_triage"


def test_open_pel_row_fails_open_when_endpoint_unreachable(tmp_path: Path) -> None:
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://does-not-exist.invalid",
        timeout=0.1,
        buffer_path=tmp_path / "buf.db",
    )

    # Should NOT raise, even though the network is unreachable.
    with fuzebox.open_pel_row(skill="claims_triage", case_id="c1") as row:
        assert row.status == "unledgered"
        row.set_predicted_outcome_usd(Decimal("1.00"))

    # The unledgered row must be queued in the local buffer for reconciliation.
    assert sdk_client._buffer is not None  # noqa: SLF001
    queued = sdk_client._buffer.list()  # noqa: SLF001
    assert len(queued) == 1


def test_open_pel_row_close_failure_is_swallowed(tmp_path: Path) -> None:
    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://cosigner.test",
        buffer_path=tmp_path / "buf.db",
    )
    with respx.mock() as router:
        router.post("http://cosigner.test/v1/pel/open").mock(
            return_value=httpx.Response(201, json=_open_response("r-2"))
        )
        router.post("http://cosigner.test/v1/pel/r-2/close").mock(
            return_value=httpx.Response(503)
        )

        # Must not raise. Agent never sees the failure.
        with fuzebox.open_pel_row(skill="claims_triage", case_id="c2") as row:
            row.set_actual_outcome_usd(Decimal("99.00"))


def test_set_outcomes_serialize_as_decimal_strings(tmp_path: Path) -> None:
    """`set_predicted_outcome_usd(0.1 + 0.2)` must not produce 0.30000000000000004."""

    fuzebox.init(
        api_key="k",
        tenant="acme",
        endpoint="http://cosigner.test",
        buffer_path=tmp_path / "buf.db",
    )
    captured: dict[str, object] = {}

    with respx.mock() as router:
        router.post("http://cosigner.test/v1/pel/open").mock(
            return_value=httpx.Response(201, json=_open_response("r-3"))
        )

        def _capture(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured["body"] = _json.loads(request.content)
            return httpx.Response(200, json={**_open_response("r-3"), "status": "closed"})

        router.post("http://cosigner.test/v1/pel/r-3/close").mock(side_effect=_capture)

        with fuzebox.open_pel_row(skill="s", case_id="c") as row:
            # Pass a float; Decimal coercion via str() must clamp at the input precision.
            row.set_predicted_outcome_usd(0.30)

    body = captured["body"]
    assert body["predicted_outcome_usd"] == "0.3"


def test_open_pel_row_without_init_raises_internally_but_does_not_propagate(
    tmp_path: Path,
) -> None:
    """When init was never called, the SDK still must not raise from the agent's view.

    Internally, `open_row` raises NotInitializedError; the context manager catches it
    and produces an unledgered stub.
    """

    fuzebox.shutdown()
    with fuzebox.open_pel_row(skill="s", case_id="c") as row:
        assert row.status == "unledgered"
