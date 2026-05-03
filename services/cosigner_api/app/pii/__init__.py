"""PII redaction at ingest."""

from .presidio_redactor import RedactionResult, redact

__all__ = ["RedactionResult", "redact"]
