"""Build an audit export bundle for a tenant.

Bundle layout:

  bundle.json     # canonical row sequence + signing material
  verify.py       # the 30-line offline verifier
  README.md       # operator instructions

`verify.py bundle.json` exits 0 iff every row hashes and verifies cleanly.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .ledger.chain import to_export_dict
from .ledger.models import PELRow
from .ledger.signing import SigningProvider

VERIFY_PY_PATH = (
    Path(__file__).resolve().parents[2] / "verify_cli" / "verify.py"
)


def build_bundle(
    rows: Iterable[PELRow],
    signer: SigningProvider,
    *,
    tenant: str,
) -> bytes:
    """Return a zip archive containing bundle.json + verify.py + README."""

    rows_export: list[dict[str, Any]] = []
    for r in rows:
        rec = to_export_dict(
            {
                "row_id": str(r.row_id),
                "tenant_id": r.tenant_id,
                "agent_id": r.agent_id,
                "skill": r.skill,
                "case_id": r.case_id,
                "model": r.model,
                "cost_usd": r.cost_usd,
                "predicted_outcome_usd": r.predicted_outcome_usd,
                "actual_outcome_usd": r.actual_outcome_usd,
                "counterfactual_outcome_usd": r.counterfactual_outcome_usd,
                "counterfactual_confidence": r.counterfactual_confidence,
                "counterfactual_method": r.counterfactual_method,
                "lift_usd": r.lift_usd,
                "trust_level": r.trust_level,
                "cosigned_by": r.cosigned_by,
                "cosigned_at": r.cosigned_at,
                "meta": r.meta or {},
                "status": r.status,
                "created_at": r.created_at,
                "closed_at": r.closed_at,
            }
        )
        rec["row_hash_hex"] = bytes(r.row_hash).hex()
        rec["signature_hex"] = bytes(r.signature).hex()
        rec["prev_hash_hex"] = bytes(r.prev_hash).hex() if r.prev_hash else None
        rows_export.append(rec)

    material = signer.public_material()
    bundle = {
        "tenant": tenant,
        "key": {
            "algorithm": material.algorithm,
            "key_id": material.key_id,
            "public_key_pem": material.public_key_pem,
            "shared_secret_b64": material.shared_secret_b64,
        },
        "rows": rows_export,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle.json", json.dumps(bundle))
        zf.writestr("verify.py", VERIFY_PY_PATH.read_text())
        zf.writestr(
            "README.md",
            (
                "# FuzeBox AEOS audit export\n\n"
                f"Tenant: {tenant}\n"
                f"Rows: {len(rows_export)}\n\n"
                "Run:\n\n    python verify.py bundle.json\n\n"
                "Exit 0 means every row's hash and signature checks out, "
                "offline, with no network access.\n"
            ),
        )
    return buf.getvalue()


__all__ = ["build_bundle"]
