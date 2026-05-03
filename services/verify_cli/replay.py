"""Replay a single case from stored spans.

Reads spans for a case_id from the cosigner's API and reconstructs the
agent's path. Useful for incident response and audit deep-dives.

Usage:
    fuzebox replay --case-id <id> [--tenant <slug>] [--endpoint <url>]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def fetch_spans(endpoint: str, tenant: str, case_id: str) -> list[dict[str, Any]]:
    url = f"{endpoint.rstrip('/')}/v1/spans"
    params = {"case_id": case_id, "tenant_id": tenant}
    with httpx.Client(timeout=10) as client:
        r = client.get(url, params=params, headers={"X-Tenant-Id": tenant})
        r.raise_for_status()
        return list(r.json().get("spans", []))


def render(spans: list[dict[str, Any]]) -> str:
    spans_sorted = sorted(spans, key=lambda s: s.get("started_at", ""))
    lines = []
    for s in spans_sorted:
        lines.append(
            f"  {s.get('started_at')} [{s.get('kind')}] {s.get('name')} "
            f"-> {s.get('attributes', {})}"
        )
    return "\n".join(lines) if lines else "  (no spans)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuzebox replay")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--endpoint", default="http://localhost:8080")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args(argv)

    try:
        spans = fetch_spans(args.endpoint, args.tenant, args.case_id)
    except httpx.HTTPError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(spans, indent=2))
    else:
        print(f"== replay case_id={args.case_id} tenant={args.tenant} ==")
        print(render(spans))
    return 0


if __name__ == "__main__":
    sys.exit(main())
