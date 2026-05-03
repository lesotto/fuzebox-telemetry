"""Audit export bundle: round-trip a 50-row chain through verify.py."""

from __future__ import annotations

import io
import subprocess
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from services.cosigner_api.app.audit_export import build_bundle
from services.cosigner_api.app.ledger.chain import compute_row_hash
from services.cosigner_api.app.ledger.signing import StaticHMACProvider


def _row(i: int, signer: StaticHMACProvider, prev: bytes | None) -> SimpleNamespace:
    payload = {
        "row_id": str(uuid.UUID(int=i + 1)),
        "tenant_id": "acme",
        "agent_id": "a",
        "skill": "claims_triage",
        "case_id": f"c-{i}",
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
        "meta": {},
        "status": "closed",
        "created_at": datetime(2026, 5, 3, 12, 0, i % 60, tzinfo=UTC),
        "closed_at": None,
    }
    link = compute_row_hash(payload, prev)
    return SimpleNamespace(
        row_id=uuid.UUID(payload["row_id"]),
        tenant_id="acme",
        agent_id="a",
        skill="claims_triage",
        case_id=f"c-{i}",
        model="gpt-4o-mini",
        cost_usd=Decimal("0.001"),
        predicted_outcome_usd=None,
        actual_outcome_usd=None,
        counterfactual_outcome_usd=None,
        counterfactual_confidence=None,
        counterfactual_method=None,
        lift_usd=None,
        trust_level=1,
        cosigned_by=None,
        cosigned_at=None,
        meta={},
        status="closed",
        created_at=payload["created_at"],
        closed_at=None,
        prev_hash=prev,
        row_hash=link.row_hash,
        signature=signer.sign(link.row_hash),
    )


def test_audit_export_round_trip(tmp_path: Path) -> None:
    signer = StaticHMACProvider(secret="audit-export-test")
    rows: list[SimpleNamespace] = []
    prev: bytes | None = None
    for i in range(50):
        r = _row(i, signer, prev)
        rows.append(r)
        prev = bytes(r.row_hash)

    blob = build_bundle(rows, signer, tenant="acme")
    bundle_path = tmp_path / "bundle.zip"
    bundle_path.write_bytes(blob)

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        zf.extractall(extracted)
    assert (extracted / "bundle.json").exists()
    assert (extracted / "verify.py").exists()
    assert (extracted / "README.md").exists()

    result = subprocess.run(
        [sys.executable, str(extracted / "verify.py"), str(extracted / "bundle.json")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verified 50" in result.stdout
