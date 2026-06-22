from __future__ import annotations


class SankhyaError(Exception):
    """Base Sankhya connector error."""


class SankhyaAuthenticationError(SankhyaError):
    """Authentication failed."""


class SankhyaTimeoutError(SankhyaError):
    """Timeout when talking to Sankhya."""


class SankhyaRateLimitError(SankhyaError):
    """Rate limit reached."""
