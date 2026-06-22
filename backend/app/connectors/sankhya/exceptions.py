from __future__ import annotations

from typing import Any


class SankhyaError(Exception):
    error_type = "unknown_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        error_type: str | None = None,
        retryable: bool | None = None,
        http_status_code: int | None = None,
        raw_error_masked: dict[str, Any] | str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_type is not None:
            self.error_type = error_type
        if retryable is not None:
            self.retryable = retryable
        self.http_status_code = http_status_code
        self.raw_error_masked = raw_error_masked


class SankhyaAuthenticationError(SankhyaError):
    error_type = "authentication_error"
    retryable = False


class SankhyaAuthorizationError(SankhyaError):
    error_type = "authorization_error"
    retryable = False


class SankhyaValidationError(SankhyaError):
    error_type = "validation_error"
    retryable = False


class SankhyaTimeoutError(SankhyaError):
    error_type = "timeout_error"
    retryable = True


class SankhyaRateLimitError(SankhyaError):
    error_type = "rate_limit_error"
    retryable = True


class SankhyaExternalAPIError(SankhyaError):
    error_type = "external_api_error"
    retryable = True


class SankhyaUnknownError(SankhyaError):
    error_type = "unknown_error"
    retryable = False
