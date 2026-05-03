# Auditor Guide — `verify.py`

The 30-line offline verifier ships in every audit export bundle. It validates
both the hash chain and the signature on every row, with no network access.

## Bundle layout

```
audit-bundle/
├── verify.py            # the verifier
└── bundle.json
```

`bundle.json` shape:

```json
{
  "key": {
    "algorithm": "HMAC-SHA256",
    "shared_secret_b64": "..."
  },
  "rows": [
    {
      "row_id": "...",
      "tenant_id": "...",
      ...               // every hashed field
      "row_hash_hex": "...",
      "signature_hex": "...",
      "prev_hash_hex": null
    }
  ]
}
```

## Run

```bash
python verify.py bundle.json
```

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | All rows verified |
| 2 | Hash mismatch on at least one row |
| 3 | Signature mismatch on at least one row |

## Performance

Validating 100 rows takes well under a second on a laptop. Sprint 1 acceptance
requires < 5 s for 100 rows; the test suite asserts this.

## Notes

- The verifier never opens a network socket.
- The only I/O is reading the bundle path you pass on the command line.
- The verifier matches the canonicalization defined in
  `services/cosigner_api/app/ledger/chain.py`. Any change to the hashed-fields
  list requires updating this file in lockstep — guarded by the round-trip
  test in `services/cosigner_api/tests/test_verify_round_trip.py`.
