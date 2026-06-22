class ApplicationError(Exception):
    """Base application exception."""


class NotFoundError(ApplicationError):
    """Resource not found."""


class ValidationError(ApplicationError):
    """Business validation error."""


class ConnectorError(ApplicationError):
    """Connector level error."""


class ConflictError(ApplicationError):
    """Conflict with current resource state."""


class DuplicateJobError(ConflictError):
    """Duplicate job detected by idempotency."""


class FlowExecutionError(ApplicationError):
    """Flow execution failed."""
