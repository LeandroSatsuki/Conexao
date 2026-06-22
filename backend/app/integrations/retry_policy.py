from __future__ import annotations

from dataclasses import dataclass

RETRYABLE_STATUS_CODES = {429} | set(range(500, 600))
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


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


def calculate_backoff(attempt: int, base_seconds: int = 2, max_seconds: int = 300) -> int:
    if attempt < 1:
        attempt = 1
    delay = base_seconds**attempt
    return min(delay, max_seconds)
