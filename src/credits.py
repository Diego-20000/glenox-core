"""Append-only credit ledger with atomic balance checks."""

from __future__ import annotations

from threading import RLock

from .exceptions import InsufficientCreditsError
from .models import CreditLedgerEntry


class CreditLedger:
    def __init__(self) -> None:
        self._entries: list[CreditLedgerEntry] = []
        self._lock = RLock()

    def grant(self, account_id: str, amount: int, reason: str) -> None:
        if amount <= 0:
            raise ValueError("grant amount must be positive")
        with self._lock:
            self._entries.append(
                CreditLedgerEntry(account_id=account_id, delta=amount, reason=reason)
            )

    def balance(self, account_id: str) -> int:
        with self._lock:
            return self._balance_unlocked(account_id)

    def can_afford(self, account_id: str, amount: int) -> bool:
        if amount <= 0:
            raise ValueError("charge amount must be positive")
        with self._lock:
            return self._balance_unlocked(account_id) >= amount

    def charge(self, account_id: str, amount: int, reason: str) -> None:
        if amount <= 0:
            raise ValueError("charge amount must be positive")
        with self._lock:
            balance = self._balance_unlocked(account_id)
            if balance < amount:
                raise InsufficientCreditsError(account_id, balance)
            self._entries.append(
                CreditLedgerEntry(account_id=account_id, delta=-amount, reason=reason)
            )

    def history(self, account_id: str) -> list[CreditLedgerEntry]:
        with self._lock:
            return [entry.model_copy(deep=True) for entry in self._entries if entry.account_id == account_id]

    def _balance_unlocked(self, account_id: str) -> int:
        return sum(entry.delta for entry in self._entries if entry.account_id == account_id)
