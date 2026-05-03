"""LocalBuffer: append / list / remove."""

from __future__ import annotations

from pathlib import Path

from fuzebox.buffer import BufferedRow, LocalBuffer


def test_append_and_list(tmp_path: Path) -> None:
    b = LocalBuffer(tmp_path / "buf.db")
    b.append(BufferedRow("r1", "acme", {"k": "v"}))
    b.append(BufferedRow("r2", "acme", {"k": "v2"}))
    rows = b.list()
    assert {r.row_id for r in rows} == {"r1", "r2"}
    b.close()


def test_remove(tmp_path: Path) -> None:
    b = LocalBuffer(tmp_path / "buf.db")
    b.append(BufferedRow("r1", "acme", {}))
    b.remove("r1")
    assert b.list() == []
    b.close()


def test_replaces_on_duplicate_id(tmp_path: Path) -> None:
    b = LocalBuffer(tmp_path / "buf.db")
    b.append(BufferedRow("r1", "acme", {"v": 1}))
    b.append(BufferedRow("r1", "acme", {"v": 2}))
    rows = b.list()
    assert len(rows) == 1
    assert rows[0].payload == {"v": 2}
    b.close()
