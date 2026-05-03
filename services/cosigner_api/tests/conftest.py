"""Shared pytest config: ensure repo root is on sys.path."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force a clean static-signing config for every test.
os.environ.setdefault("FUZEBOX_SIGNING_PROVIDER", "static")
os.environ.setdefault("FUZEBOX_STATIC_SIGNING_KEY", "test-secret")
os.environ.setdefault("FUZEBOX_ENVIRONMENT", "dev")
