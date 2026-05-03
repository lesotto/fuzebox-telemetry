"""Replay CLI smoke test: render fetched spans."""

from __future__ import annotations

from services.verify_cli.replay import render


def test_render_orders_by_started_at() -> None:
    spans = [
        {"started_at": "2026-05-03T12:00:01Z", "name": "b", "kind": "tool"},
        {"started_at": "2026-05-03T12:00:00Z", "name": "a", "kind": "llm"},
    ]
    out = render(spans)
    assert out.index("a") < out.index("b")


def test_render_empty() -> None:
    assert "no spans" in render([])
