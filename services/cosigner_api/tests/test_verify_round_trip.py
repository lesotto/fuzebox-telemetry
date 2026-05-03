"""End-to-end test for `verify.py`: build a 100-row chain with the same logic
the repo uses, write a bundle, run `verify.py` as a subprocess, assert exit 0.

Per Sprint 1 acceptance: `verify.py` validates a chain produced by the SDK in
under 5 seconds. We assert under 5s here too.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from services.cosigner_api.app.ledger.chain import compute_row_hash, to_export_dict
from services.cosigner_api.app.ledger.signing import StaticHMACProvider

ROOT = Path(__file__).resolve().parents[3]
VERIFY = ROOT / "services" / "verify_cli" / "verify.py"


def _build_chain(n: int, signer: StaticHMACProvider) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    prev: bytes | None = None
    for i in range(n):
        r = {
            "row_id": str(uuid.UUID(int=i + 1)),
            "tenant_id": "acme",
            "agent_id": "a1",
            "skill": "claims_triage",
            "case_id": f"case-{i}",
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
            "meta": {"i": i},
            "status": "closed",
            "created_at": datetime(2026, 5, 3, 12, 0, i % 60, tzinfo=UTC),
            "closed_at": None,
        }
        link = compute_row_hash(r, prev)
        sig = signer.sign(link.row_hash)
        # Build the export-shape row.
        export = to_export_dict(r)
        export["row_hash_hex"] = link.row_hash.hex()
        export["signature_hex"] = sig.hex()
        export["prev_hash_hex"] = prev.hex() if prev else None
        rows.append(export)
        prev = link.row_hash
    return rows


def test_verify_validates_100_row_chain(tmp_path: Path) -> None:
    signer = StaticHMACProvider(secret="audit-secret")
    rows = _build_chain(100, signer)
    bundle = {
        "key": {
            "algorithm": "HMAC-SHA256",
            "shared_secret_b64": base64.b64encode(b"audit-secret").decode("ascii"),
        },
        "rows": rows,
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle))

    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(VERIFY), str(bundle_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    elapsed = time.perf_counter() - started

    assert result.returncode == 0, f"verify.py failed: {result.stdout} {result.stderr}"
    assert "verified 100" in result.stdout
    assert elapsed < 5.0, f"verify.py took {elapsed:.2f}s, expected <5s"


def test_verify_detects_tamper(tmp_path: Path) -> None:
    signer = StaticHMACProvider(secret="audit-secret")
    rows = _build_chain(10, signer)
    rows[5]["case_id"] = "tampered"  # changed *after* the chain was sealed
    bundle = {
        "key": {
            "algorithm": "HMAC-SHA256",
            "shared_secret_b64": base64.b64encode(b"audit-secret").decode("ascii"),
        },
        "rows": rows,
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle))

    result = subprocess.run(
        [sys.executable, str(VERIFY), str(bundle_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "mismatch" in result.stdout
