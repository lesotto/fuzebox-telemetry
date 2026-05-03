"""Sprint 1 demo: SDK opens 100 rows; chain is signed; verify.py validates.

Run from repo root:

    python scripts/sprint1_demo.py

This avoids needing a running Postgres — it exercises the canonical hashing,
signing, chain extension, and the offline verifier exactly as the production
system does. Ledger persistence + RLS are exercised separately by the
`test_repo_postgres.py` integration suite.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.cosigner_api.app.ledger.chain import compute_row_hash, to_export_dict
from services.cosigner_api.app.ledger.signing import StaticHMACProvider


def main() -> int:
    print("== Sprint 1 demo ==")
    signer = StaticHMACProvider(secret="sprint1-demo-secret")
    rows: list[dict[str, object]] = []
    prev: bytes | None = None

    started = time.perf_counter()
    for i in range(100):
        row = {
            "row_id": str(uuid.UUID(int=i + 1)),
            "tenant_id": "acme",
            "agent_id": "claims-bot",
            "skill": "claims_triage",
            "case_id": f"case-{i}",
            "model": "gpt-4o-mini",
            "cost_usd": Decimal("0.0009"),
            "predicted_outcome_usd": Decimal("50.00") if i % 3 == 0 else None,
            "actual_outcome_usd": None,
            "counterfactual_outcome_usd": None,
            "counterfactual_confidence": None,
            "counterfactual_method": None,
            "lift_usd": None,
            "trust_level": 1,
            "cosigned_by": None,
            "cosigned_at": None,
            "meta": {"stripe_payment_intent_id": f"pi_{i}"},
            "status": "closed",
            "created_at": datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
            "closed_at": None,
        }
        link = compute_row_hash(row, prev)
        sig = signer.sign(link.row_hash)
        export = to_export_dict(row)
        export["row_hash_hex"] = link.row_hash.hex()
        export["signature_hex"] = sig.hex()
        export["prev_hash_hex"] = prev.hex() if prev else None
        rows.append(export)
        prev = link.row_hash

    chain_elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"  built 100-row signed chain in {chain_elapsed_ms:.1f} ms")

    bundle = {
        "key": {
            "algorithm": "HMAC-SHA256",
            "shared_secret_b64": base64.b64encode(b"sprint1-demo-secret").decode(),
        },
        "rows": rows,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bundle, f)
        bundle_path = f.name

    print(f"  wrote bundle: {bundle_path}")

    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(ROOT / "services/verify_cli/verify.py"), bundle_path],
        capture_output=True,
        text=True,
        timeout=10,
    )
    verify_elapsed = time.perf_counter() - started
    print(f"  verify.py exit={result.returncode} elapsed={verify_elapsed:.3f}s")
    print(f"  verify.py stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"  verify.py stderr: {result.stderr.strip()}")

    print()
    print("== Tampering check ==")
    rows[42]["case_id"] = "TAMPERED"
    bundle["rows"] = rows
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bundle, f)
        tampered_path = f.name
    result2 = subprocess.run(
        [sys.executable, str(ROOT / "services/verify_cli/verify.py"), tampered_path],
        capture_output=True,
        text=True,
        timeout=10,
    )
    print(f"  verify.py (tampered) exit={result2.returncode}")
    print(f"  verify.py stdout: {result2.stdout.strip()}")

    ok = (
        result.returncode == 0
        and verify_elapsed < 5.0
        and result2.returncode != 0
    )
    print()
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
