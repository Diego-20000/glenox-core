"""An append-only credit ledger.

Balances are never stored or mutated directly — they're always the sum
of every entry ever recorded for an account. That makes the balance
trivially auditable (replay the entries, get the number) and makes a
double-charge bug visible as a duplicate entry in history instead of an
untraceable off-by-one in some mutable counter.
"""

from __future__ import annotations

from .exceptions import InsufficientCreditsError
from .models import CreditLedgerEntry


class CreditLedger:
    def __init__(self) -> None:
        self._entries: list[CreditLedgerEntry] = []

    def grant(self, account_id: str, amount: int, reason: str) -> None:
        self._entries.append(CreditLedgerEntry(account_id=account_id, delta=amount, reason=reason))

    def balance(self, account_id: str) -> int:
        return sum(e.delta for e in self._entries if e.account_id == account_id)

    def can_afford(self, account_id: str, amount: int) -> bool:
        return self.balance(account_id) >= amount

    def charge(self, account_id: str, amount: int, reason: str) -> None:
        if not self.can_afford(account_id, amount):
            raise InsufficientCreditsError(account_id, self.balance(account_id))
        self._entries.append(CreditLedgerEntry(account_id=account_id, delta=-amount, reason=reason))

    def history(self, account_id: str) -> list[CreditLedgerEntry]:
        return [e for e in self._entries if e.account_id == account_id]
