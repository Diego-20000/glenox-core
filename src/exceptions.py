"""Error hierarchy for the routing engine, rooted at GlenoxCoreError so
callers can catch broadly or narrowly without ever needing a bare `except`."""

from __future__ import annotations


class GlenoxCoreError(Exception):
    """Base class for all errors raised by this package."""


class AllProvidersExhaustedError(GlenoxCoreError):
    """Raised when every provider in the fallback chain failed or was
    skipped (e.g. insufficient credits for all of them)."""

    def __init__(self, attempted: list[str], reasons: list[str]) -> None:
        self.attempted = attempted
        self.reasons = reasons
        detail = "; ".join(f"{p}: {r}" for p, r in zip(attempted, reasons))
        super().__init__(f"no provider could serve the request ({detail})")


class InsufficientCreditsError(GlenoxCoreError):
    """Raised when an account has no credits left for even the cheapest
    provider in its allowed tier."""

    def __init__(self, account_id: str, balance: int) -> None:
        self.account_id = account_id
        self.balance = balance
        super().__init__(f"account {account_id} has insufficient credits (balance={balance})")


class ProviderError(GlenoxCoreError):
    """Wraps a single provider call failure (timeout, rate limit, bad
    response) so the router can log it and move to the next provider
    without leaking provider-specific exception types upward."""

    def __init__(self, provider_name: str, reason: str) -> None:
        self.provider_name = provider_name
        self.reason = reason
        super().__init__(f"{provider_name} failed: {reason}")
