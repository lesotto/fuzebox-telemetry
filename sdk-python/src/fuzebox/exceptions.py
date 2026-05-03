"""SDK-only exceptions. Internal failures never leak past the context manager."""


class FuzeboxError(Exception):
    """Base class for SDK errors."""


class NotInitializedError(FuzeboxError):
    """Raised when SDK calls happen before `fuzebox.init`."""
