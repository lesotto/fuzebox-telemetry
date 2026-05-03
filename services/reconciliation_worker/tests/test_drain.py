"""drain_buffered: post each buffered row, count successes / failures."""

from __future__ import annotations

import pytest

from services.reconciliation_worker.tasks import drain_buffered


def test_drain_all_succeed() -> None:
    posted: list[dict] = []
    stats = drain_buffered([{"a": 1}, {"a": 2}], post_open=lambda p: posted.append(p))
    assert stats.queued == 2
    assert stats.posted == 2
    assert stats.failed == 0
    assert posted == [{"a": 1}, {"a": 2}]


def test_drain_records_failures() -> None:
    def flaky(p):
        if p["a"] == 2:
            raise RuntimeError("nope")

    stats = drain_buffered([{"a": 1}, {"a": 2}, {"a": 3}], post_open=flaky)
    assert stats.queued == 3
    assert stats.posted == 2
    assert stats.failed == 1


def test_drain_empty() -> None:
    stats = drain_buffered([], post_open=lambda _p: None)
    assert stats == type(stats)(queued=0, posted=0, failed=0)


@pytest.mark.parametrize("n", [1, 10, 100])
def test_drain_scales(n: int) -> None:
    rows = [{"i": i} for i in range(n)]
    seen: list[dict] = []
    stats = drain_buffered(rows, post_open=lambda p: seen.append(p))
    assert stats.queued == stats.posted == n
    assert seen == rows
