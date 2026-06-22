from __future__ import annotations

from app.integrations.retry_policy import calculate_backoff, should_retry


def test_retry_policy_matches_expected_status_codes():
    assert should_retry(500) is True
    assert should_retry(429) is True
    assert should_retry(400) is False
    assert should_retry(401) is False


def test_retry_policy_backoff_grows_with_attempts():
    assert calculate_backoff(1) == 2
    assert calculate_backoff(2) == 4
    assert calculate_backoff(8) <= 300
