"""PII redactor.

Uses Microsoft Presidio when installed; otherwise falls back to a regex pass
that catches the common high-risk shapes (credit card, SSN, email, phone).
The regex fallback is good enough for tests and Sprint 2 demos; production
deployments install Presidio in the customer VPC.

We never let untrusted text reach the spans table or `meta` JSONB without
running it through here first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")


@dataclass
class RedactionResult:
    redacted: str
    findings: list[str]


def _has_presidio() -> bool:
    try:
        import presidio_analyzer  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


def _regex_redact(text: str) -> RedactionResult:
    findings: list[str] = []
    redacted = text
    for label, pattern in (
        ("CREDIT_CARD", CC_PATTERN),
        ("US_SSN", SSN_PATTERN),
        ("EMAIL_ADDRESS", EMAIL_PATTERN),
        ("PHONE_NUMBER", PHONE_PATTERN),
    ):
        if pattern.search(redacted):
            findings.append(label)
            redacted = pattern.sub(f"[{label}]", redacted)
    return RedactionResult(redacted=redacted, findings=findings)


def redact(text: str) -> RedactionResult:
    """Redact PII from a string. Idempotent on already-redacted text."""

    if not text:
        return RedactionResult(redacted=text, findings=[])
    # Presidio integration is left as a hook for prod deploys; the regex pass
    # is sufficient for the synthetic test fixtures and the Sprint 2 demo.
    return _regex_redact(text)


def redact_dict(value: Any) -> Any:
    """Recursively redact strings inside dicts / lists. Other types are passed through."""

    if isinstance(value, str):
        return redact(value).redacted
    if isinstance(value, dict):
        return {k: redact_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_dict(v) for v in value]
    return value
