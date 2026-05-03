"""SDK hot-path microbenchmark.

Measures `open_pel_row` overhead with the cosigner endpoint stubbed locally.
Sprint 5 turns the budget (5 ms p99 at 1k req/s) into a CI gate. For now
this prints the numbers as an advisory.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk-python" / "src"))

import fuzebox  # noqa: E402
from fuzebox import client as sdk_client  # noqa: E402


def run(n: int = 1000) -> None:
    fuzebox.init(
        api_key="bench",
        tenant="bench",
        endpoint="http://127.0.0.1:1",  # closed port
        timeout=0.05,
        buffer_path=ROOT / ".bench-buffer.db",
    )

    # Patch transport to be a no-op so we measure the SDK overhead, not network.
    def fake_open(payload):  # type: ignore[no-untyped-def]
        return {
            "row_id": "00000000-0000-0000-0000-000000000001",
            "tenant_id": "bench",
            "agent_id": "x",
            "skill": payload.get("skill", "s"),
            "case_id": payload.get("case_id", "c"),
            "status": "open",
            "trust_level": 1,
        }

    def fake_close(_row_id, _payload):  # type: ignore[no-untyped-def]
        return None

    sdk_client.open_row = fake_open  # type: ignore[assignment]
    sdk_client.close_row = fake_close  # type: ignore[assignment]

    samples: list[float] = []
    for i in range(n):
        t0 = time.perf_counter()
        with fuzebox.open_pel_row(skill="bench", case_id=f"c-{i}"):
            pass
        samples.append((time.perf_counter() - t0) * 1000)

    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(len(samples) * 0.95)]
    p99 = samples[int(len(samples) * 0.99)]
    print(f"open_pel_row n={n} p50={p50:.3f}ms p95={p95:.3f}ms p99={p99:.3f}ms")


if __name__ == "__main__":
    run(1000)
