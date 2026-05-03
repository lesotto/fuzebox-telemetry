"""Sprint 5 demo: build a 100-row audit bundle, write it as a zip, extract it,
run verify.py from inside the bundle. Drain a queue of synthetic buffered
rows and print the reconciliation stats.
"""

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.cosigner_api.app.audit_export import build_bundle
from services.cosigner_api.app.ledger.chain import compute_row_hash
from services.cosigner_api.app.ledger.signing import StaticHMACProvider
from services.reconciliation_worker.tasks import drain_buffered


def main() -> int:
    print("== Sprint 5 demo ==")

    signer = StaticHMACProvider(secret="sprint5-demo")
    rows: list[SimpleNamespace] = []
    prev: bytes | None = None
    for i in range(100):
        payload = {
            "row_id": str(uuid.UUID(int=i + 1)),
            "tenant_id": "acme",
            "agent_id": "claims-bot",
            "skill": "claims_triage",
            "case_id": f"case-{i}",
            "model": "gpt-4o-mini",
            "cost_usd": Decimal("0.001"),
            "predicted_outcome_usd": Decimal("50") if i % 2 == 0 else None,
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
            "created_at": datetime(2026, 5, 3, 12, 0, i % 60, tzinfo=UTC),
            "closed_at": None,
        }
        link = compute_row_hash(payload, prev)
        sig = signer.sign(link.row_hash)
        rows.append(
            SimpleNamespace(
                **payload,
                prev_hash=prev,
                row_hash=link.row_hash,
                signature=sig,
                row_id_uuid=uuid.UUID(payload["row_id"]),
            )
        )
        prev = link.row_hash

    # SimpleNamespace stringifies row_id; we need uuid.UUID for the export. Patch:
    for r in rows:
        r.row_id = r.row_id_uuid

    zip_bytes = build_bundle(rows, signer, tenant="acme")
    out_dir = Path("/tmp/fuzebox-sprint5-bundle")
    out_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(out_dir)
    print(f"  wrote bundle -> {out_dir} (files: {[p.name for p in out_dir.iterdir()]})")

    result = subprocess.run(
        [sys.executable, str(out_dir / "verify.py"), str(out_dir / "bundle.json")],
        capture_output=True,
        text=True,
    )
    print(f"  verify.py exit={result.returncode} stdout={result.stdout.strip()}")

    # Reconciliation
    posted: list[dict] = []
    stats = drain_buffered(
        [
            {"agent_id": "x", "skill": "s", "case_id": f"c{i}"} for i in range(7)
        ],
        post_open=lambda p: posted.append(p),
    )
    print(f"  reconciliation: queued={stats.queued} posted={stats.posted} failed={stats.failed}")

    ok = result.returncode == 0 and stats.posted == 7
    print()
    print("RESULT:", "PASS ✓" if ok else "FAIL ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
