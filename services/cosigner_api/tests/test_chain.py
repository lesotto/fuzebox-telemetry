"""Tests for the canonical hash + chain primitives."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from services.cosigner_api.app.ledger.chain import (
    canonicalize_row,
    compute_row_hash,
    to_export_dict,
    verify_row,
)


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "row_id": str(uuid.UUID(int=1)),
        "tenant_id": "acme",
        "agent_id": "a1",
        "skill": "claims_triage",
        "case_id": "c1",
        "model": "gpt-4o-mini",
        "cost_usd": Decimal("0.001"),
        "predicted_outcome_usd": None,
        "actual_outcome_usd": None,
        "counterfactual_outcome_usd": None,
        "counterfactual_confidence": None,
        "counterfactual_method": None,
        "lift_usd": None,
        "trust_level": 1,
        "cosigned_by": None,
        "cosigned_at": None,
        "meta": {"k": "v"},
        "status": "open",
        "created_at": datetime(2026, 5, 3, tzinfo=UTC),
        "closed_at": None,
    }
    base.update(overrides)
    return base


def test_canonicalize_is_stable() -> None:
    a = canonicalize_row(_row(meta={"a": 1, "b": 2}))
    b = canonicalize_row(_row(meta={"b": 2, "a": 1}))
    assert a == b


def test_canonicalize_uses_sorted_top_level() -> None:
    payload = canonicalize_row(_row())
    # Strict ASCII sorted order at top level.
    keys_in_order = []
    s = payload.decode()
    i = 0
    while i < len(s):
        if s[i] == '"':
            end = s.index('"', i + 1)
            keys_in_order.append(s[i + 1 : end])
            i = end + 1
            # find matching ':' or skip
        i += 1
    # The first key should be the lexicographically smallest of the hashed fields.
    assert keys_in_order[0] == "actual_outcome_usd"


def test_chain_links_propagate() -> None:
    r1 = _row()
    link1 = compute_row_hash(r1, prev_hash=None)
    r2 = _row(row_id=str(uuid.UUID(int=2)), case_id="c2")
    link2 = compute_row_hash(r2, prev_hash=link1.row_hash)
    assert link1.row_hash != link2.row_hash
    assert link2.prev_hash == link1.row_hash


def test_verify_row_round_trip() -> None:
    r = _row()
    link = compute_row_hash(r, prev_hash=None)
    assert verify_row(r, prev_hash=None, expected_row_hash=link.row_hash)


def test_verify_row_detects_tamper() -> None:
    r = _row()
    link = compute_row_hash(r, prev_hash=None)
    tampered = dict(r)
    tampered["case_id"] = "c-tampered"
    assert not verify_row(tampered, prev_hash=None, expected_row_hash=link.row_hash)


def test_floats_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize_row(_row(cost_usd=0.001))  # type: ignore[arg-type]


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        canonicalize_row(_row(created_at=datetime(2026, 5, 3)))  # type: ignore[arg-type]


def test_to_export_dict_round_trips() -> None:
    """to_export_dict + json.dumps must reproduce canonicalize_row bytes."""
    import json

    r = _row()
    canon = canonicalize_row(r)
    export = to_export_dict(r)
    re_encoded = json.dumps(export, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert canon == re_encoded


@given(seed=st.integers(min_value=0, max_value=10_000))
@hsettings(deadline=None, max_examples=30)
def test_chain_property_extends_uniquely(seed: int) -> None:
    prev = None
    seen = set()
    for i in range(5):
        r = _row(row_id=str(uuid.UUID(int=seed * 1000 + i)), case_id=f"case-{i}")
        link = compute_row_hash(r, prev_hash=prev)
        assert link.row_hash not in seen
        seen.add(link.row_hash)
        prev = link.row_hash
