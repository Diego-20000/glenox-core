"""Error types raised by the routing engine."""

from __future__ import annotations


class GlenoxCoreError(Exception):
    """Base class for all package errors."""


class UnknownAccountError(GlenoxCoreError):
    """Raised when a request references an account without a registered plan."""

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        super().__init__(f"unknown account: {account_id}")


class AllProvidersExhaustedError(GlenoxCoreError):
    def __init__(self, attempted: list[str], reasons: list[str]) -> None:
        self.attempted = attempted
        self.reasons = reasons
        detail = "; ".join(f"{p}: {r}" for p, r in zip(attempted, reasons))
        super().__init__(f"no provider could serve the request ({detail})")


class InsufficientCreditsError(GlenoxCoreError):
    def __init__(self, account_id: str, balance: int) -> None:
        self.account_id = account_id
        self.balance = balance
        super().__init__(f"account {account_id} has insufficient credits (balance={balance})")


class ProviderError(GlenoxCoreError):
    def __init__(self, provider_name: str, reason: str) -> None:
        self.provider_name = provider_name
        self.reason = reason
        super().__init__(f"{provider_name} failed: {reason}")
