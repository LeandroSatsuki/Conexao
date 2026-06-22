from __future__ import annotations

from dataclasses import dataclass

RETRYABLE_STATUS_CODES = {429} | set(range(500, 600))
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}
RETRYABLE_ERROR_TYPES = {"timeout_error", "rate_limit_error", "external_api_error"}
NON_RETRYABLE_ERROR_TYPES = {"validation_error", "mapping_error", "authentication_error", "business_rule_error"}


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: int


def should_retry(status_code: int | None = None, error_type: str | None = None) -> bool:
    if status_code is not None:
        if status_code in NON_RETRYABLE_STATUS_CODES:
            return False
        if status_code in RETRYABLE_STATUS_CODES:
            return True
    if error_type in {"timeout_error", "rate_limit_error", "external_api_error"}:
        return True
    return False


def classify_execution_exception(error: Exception | None = None, error_type: str | None = None) -> RetryDecision:
    resolved_type = error_type
    if resolved_type is None and error is not None:
        resolved_type = error.__class__.__name__.replace("Error", "").lower()
    if resolved_type in RETRYABLE_ERROR_TYPES:
        return RetryDecision(retry=True, delay_seconds=calculate_backoff(1))
    if resolved_type in NON_RETRYABLE_ERROR_TYPES:
        return RetryDecision(retry=False, delay_seconds=0)
    return RetryDecision(retry=should_retry(error_type=resolved_type), delay_seconds=calculate_backoff(1))


def calculate_backoff(attempt: int, base_seconds: int = 2, max_seconds: int = 300) -> int:
    if attempt < 1:
        attempt = 1
    delay = base_seconds**attempt
    return min(delay, max_seconds)
