#!/usr/bin/env python3
"""Offline verifier for a FuzeBox audit export bundle.

Usage: python verify.py <bundle.json>

Bundle format (the cosigner's audit export emits this verbatim):

    {
      "key": {"algorithm": "HMAC-SHA256", "shared_secret_b64": "..."},
      "rows": [ {<canonical row fields>, "row_hash_hex": "...", "signature_hex": "...", "prev_hash_hex": null}, ... ]
    }

Exit 0 on success. Non-zero on any chain or signature failure.
"""
import base64
import hashlib
import hmac
import json
import sys

F = ("row_id","tenant_id","agent_id","skill","case_id","model","cost_usd",
     "predicted_outcome_usd","actual_outcome_usd","counterfactual_outcome_usd",
     "counterfactual_confidence","counterfactual_method","lift_usd","trust_level",
     "cosigned_by","cosigned_at","meta","status","created_at","closed_at")

def main(path):
    bundle = json.loads(open(path).read())
    secret = base64.b64decode(bundle["key"]["shared_secret_b64"])
    prev = None
    for i, row in enumerate(bundle["rows"]):
        canon = json.dumps({f: row.get(f) for f in F}, sort_keys=True, separators=(",", ":")).encode()
        h = hashlib.sha256(); h.update(canon)
        if prev is not None: h.update(prev)
        rh = h.digest()
        if rh.hex() != row["row_hash_hex"]:
            print(f"row {i}: hash mismatch"); sys.exit(2)
        sig = hmac.new(secret, rh, hashlib.sha256).digest()
        if not hmac.compare_digest(sig.hex(), row["signature_hex"]):
            print(f"row {i}: signature mismatch"); sys.exit(3)
        prev = rh
    print(f"OK: verified {len(bundle['rows'])} rows"); sys.exit(0)

if __name__ == "__main__":
    main(sys.argv[1])
