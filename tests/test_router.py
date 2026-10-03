"""Unit tests for the routing engine: fallback behavior, credit
enforcement, and ledger auditability."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.credits import CreditLedger
from src.exceptions import AllProvidersExhaustedError, InsufficientCreditsError, UnknownAccountError
from src.models import CompletionRequest, ProviderSpec, ProviderTier
from src.providers import AlwaysFailsProvider, EchoProvider, UnreliableProvider
from src.router import CompletionRouter


def _router_with_credits(balance: int = 100) -> tuple[CompletionRouter, CreditLedger]:
    ledger = CreditLedger()
    ledger.grant("acct-1", balance, reason="signup bonus")
    router = CompletionRouter(ledger)
    router.register_account("acct-1", ProviderTier.PREMIUM)
    return router, ledger


class TestHappyPath:
    def test_single_provider_serves_and_charges(self) -> None:
        router, ledger = _router_with_credits(balance=10)
        router.register(
            ProviderSpec(name="echo", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            EchoProvider("echo"),
        )

        result = router.route(CompletionRequest(account_id="acct-1", prompt="hola"))

        assert result.served_by == "echo"
        assert result.credits_charged == 1
        assert result.attempts == []
        assert ledger.balance("acct-1") == 9


class TestFallback:
    def test_falls_through_to_second_provider_on_failure(self) -> None:
        router, ledger = _router_with_credits(balance=10)
        router.register(
            ProviderSpec(name="flaky", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            AlwaysFailsProvider("flaky"),
        )
        router.register(
            ProviderSpec(name="backup", tier=ProviderTier.FREE, credit_weight=2, priority=1),
            EchoProvider("backup"),
        )

        result = router.route(CompletionRequest(account_id="acct-1", prompt="hola"))

        assert result.served_by == "backup"
        assert result.attempts == ["flaky"]
        assert ledger.balance("acct-1") == 8  # only charged for the provider that actually served it

    def test_recovers_after_transient_failures(self) -> None:
        router, _ = _router_with_credits(balance=10)
        router.register(
            ProviderSpec(name="unreliable", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            UnreliableProvider("unreliable", fail_times=2),
        )
        request = CompletionRequest(account_id="acct-1", prompt="hola", request_id="req-1")

        # Same provider instance across calls: first two fail (simulated
        # transient outage), the third succeeds once it "recovers".
        with pytest.raises(AllProvidersExhaustedError):
            router.route(request)
        with pytest.raises(AllProvidersExhaustedError):
            router.route(request)
        result = router.route(request)

        assert result.served_by == "unreliable"

    def test_all_providers_exhausted_raises_with_reasons(self) -> None:
        router, _ = _router_with_credits(balance=10)
        router.register(
            ProviderSpec(name="dead-a", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            AlwaysFailsProvider("dead-a"),
        )
        router.register(
            ProviderSpec(name="dead-b", tier=ProviderTier.FREE, credit_weight=1, priority=1),
            AlwaysFailsProvider("dead-b"),
        )

        with pytest.raises(AllProvidersExhaustedError) as excinfo:
            router.route(CompletionRequest(account_id="acct-1", prompt="hola"))

        assert excinfo.value.attempted == ["dead-a", "dead-b"]


class TestCreditGovernance:
    def test_skips_provider_account_cannot_afford(self) -> None:
        # Both providers share a tier so ordering is decided by priority
        # alone — isolates the credit-skip behavior from tier ordering.
        router, _ = _router_with_credits(balance=1)
        router.register(
            ProviderSpec(name="expensive", tier=ProviderTier.FREE, credit_weight=10, priority=0),
            EchoProvider("expensive"),
        )
        router.register(
            ProviderSpec(name="cheap", tier=ProviderTier.FREE, credit_weight=1, priority=1),
            EchoProvider("cheap"),
        )

        result = router.route(CompletionRequest(account_id="acct-1", prompt="hola"))

        assert result.served_by == "cheap"
        assert result.attempts == ["expensive"]

    def test_tier_ceiling_excludes_providers_above_it(self) -> None:
        router, _ = _router_with_credits(balance=100)
        router.register(
            ProviderSpec(name="premium-only", tier=ProviderTier.PREMIUM, credit_weight=1, priority=0),
            EchoProvider("premium-only"),
        )
        router.register_account("acct-1", ProviderTier.FREE)

        with pytest.raises(AllProvidersExhaustedError) as excinfo:
            router.route(CompletionRequest(account_id="acct-1", prompt="hola"))

        assert excinfo.value.attempted == []  # never even considered — filtered before the loop

    def test_charge_raises_when_balance_would_go_negative(self) -> None:
        ledger = CreditLedger()
        ledger.grant("acct-1", 5, reason="bonus")
        with pytest.raises(InsufficientCreditsError):
            ledger.charge("acct-1", 10, reason="too expensive")


class TestLedgerAuditability:
    def test_balance_is_derived_from_history(self) -> None:
        ledger = CreditLedger()
        ledger.grant("acct-1", 100, reason="signup")
        ledger.charge("acct-1", 30, reason="completion")
        ledger.charge("acct-1", 20, reason="completion")

        assert ledger.balance("acct-1") == 50
        assert len(ledger.history("acct-1")) == 3
        assert sum(e.delta for e in ledger.history("acct-1")) == ledger.balance("acct-1")


class TestModelValidation:
    def test_blank_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompletionRequest(account_id="acct-1", prompt="   ")

    def test_provider_spec_requires_positive_weight(self) -> None:
        with pytest.raises(ValidationError):
            ProviderSpec(name="x", tier=ProviderTier.FREE, credit_weight=0, priority=0)


class TestHardening:
    def test_request_cannot_use_an_unregistered_account(self) -> None:
        ledger = CreditLedger()
        router = CompletionRouter(ledger)
        router.register(
            ProviderSpec(name="echo", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            EchoProvider("echo"),
        )
        with pytest.raises(UnknownAccountError):
            router.route(CompletionRequest(account_id="acct-404", prompt="hola"))

    def test_duplicate_provider_names_are_rejected(self) -> None:
        router, _ = _router_with_credits()
        router.register(
            ProviderSpec(name="echo", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            EchoProvider("echo"),
        )
        with pytest.raises(ValueError, match="already registered"):
            router.register(
                ProviderSpec(name="echo", tier=ProviderTier.FREE, credit_weight=1, priority=1),
                EchoProvider("echo-2"),
            )

    def test_repeated_request_id_does_not_charge_twice(self) -> None:
        router, ledger = _router_with_credits(balance=10)
        router.register(
            ProviderSpec(name="echo", tier=ProviderTier.FREE, credit_weight=1, priority=0),
            EchoProvider("echo"),
        )
        request = CompletionRequest(account_id="acct-1", prompt="hola", request_id="same-request")
        first = router.route(request)
        second = router.route(request)

        assert first == second
        assert ledger.balance("acct-1") == 9

    def test_grant_rejects_zero_or_negative_amount(self) -> None:
        ledger = CreditLedger()
        with pytest.raises(ValueError):
            ledger.grant("acct-1", 0, reason="bonus")
        with pytest.raises(ValueError):
            ledger.grant("acct-1", -1, reason="bonus")
