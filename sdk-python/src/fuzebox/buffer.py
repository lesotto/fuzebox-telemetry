"""Local SQLite buffer for fail-open semantics.

If the cosigner endpoint is unreachable, every row gets persisted here with
status=`unledgered`. A background flusher (Sprint 5) drains the buffer once the
endpoint recovers. Sprint 1 implements only the buffer primitives so the SDK
hot path can rely on them.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# 100 MB cap, per the prompt.
_MAX_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class BufferedRow:
    """A row that hasn't been confirmed by the cosigner yet."""

    row_id: str
    tenant_id: str
    payload: dict[str, Any]


class LocalBuffer:
    """Thread-safe SQLite-backed buffer.

    Example:
        >>> import tempfile, pathlib
        >>> tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        >>> b = LocalBuffer(pathlib.Path(tmp.name))
        >>> b.append(BufferedRow("r1", "acme", {"k": "v"}))
        >>> [r.row_id for r in b.list()]
        ['r1']
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS buffered_rows (
              row_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              payload TEXT NOT NULL,
              ts INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
            )
            """
        )

    def append(self, row: BufferedRow) -> None:
        with self._lock:
            if self._size_bytes() > _MAX_BYTES:
                self._evict_oldest()
            self._conn.execute(
                "INSERT OR REPLACE INTO buffered_rows "
                "(row_id, tenant_id, payload) VALUES (?, ?, ?)",
                (row.row_id, row.tenant_id, json.dumps(row.payload)),
            )

    def remove(self, row_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM buffered_rows WHERE row_id = ?", (row_id,))

    def list(self) -> list[BufferedRow]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT row_id, tenant_id, payload FROM buffered_rows ORDER BY ts ASC"
            )
            return [
                BufferedRow(row_id=r[0], tenant_id=r[1], payload=json.loads(r[2]))
                for r in cursor.fetchall()
            ]

    def _size_bytes(self) -> int:
        try:
            return self._path.stat().st_size
        except FileNotFoundError:
            return 0

    def _evict_oldest(self) -> None:
        # Evict ~10% of buffered rows when over limit.
        self._conn.execute(
            """
            DELETE FROM buffered_rows
            WHERE row_id IN (
              SELECT row_id FROM buffered_rows ORDER BY ts ASC LIMIT
                (SELECT MAX(1, COUNT(*) / 10) FROM buffered_rows)
            )
            """
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["BufferedRow", "LocalBuffer", "asdict"]
