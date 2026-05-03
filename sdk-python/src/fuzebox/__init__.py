"""FuzeBox SDK — public API.

Two surfaces:

- `init(api_key=..., tenant=..., endpoint=...)` — configure the SDK.
- `open_pel_row(...)` — context manager that records a single execution.

Both are safe to call from arbitrary entry points; `init` is idempotent.
"""

from __future__ import annotations

from .client import init, shutdown
from .exceptions import FuzeboxError, NotInitializedError
from .pel import PELRow, open_pel_row

__all__ = [
    "FuzeboxError",
    "NotInitializedError",
    "PELRow",
    "init",
    "open_pel_row",
    "shutdown",
]

__version__ = "0.1.0"
