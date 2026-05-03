"""Core error types for EarnApp Bot."""


class EarnAppError(Exception):
    """Base class for application-level errors."""


class RuntimeConfigError(EarnAppError):
    """Raised when runtime configuration cannot be resolved."""


class StorageError(EarnAppError):
    """Raised when runtime storage cannot be read or written safely."""
