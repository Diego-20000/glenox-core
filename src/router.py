"""Multi-provider completion router with automatic fallback and
credit-aware cost governance.

The core idea: a chatbot backed by a single LLM provider goes down when
that provider does, and a naive "just call the cheapest model" approach
lets one account's traffic burn through budget meant for everyone. This
router solves both by walking an ordered chain of providers — cheapest
and most permissive first — skipping any the account can't afford, and
falling through to the next one on failure, all while every credit
movement lands in an auditable ledger.
"""

from __future__ import annotations

from .credits import CreditLedger
from .exceptions import AllProvidersExhaustedError, ProviderError
from .models import CompletionRequest, CompletionResult, ProviderSpec, ProviderTier
from .providers import CompletionProvider

_TIER_ORDER: dict[ProviderTier, int] = {
    ProviderTier.FREE: 0,
    ProviderTier.STANDARD: 1,
    ProviderTier.PREMIUM: 2,
}


class CompletionRouter:
    def __init__(self, ledger: CreditLedger) -> None:
        self._ledger = ledger
        self._specs: list[ProviderSpec] = []
        self._impls: dict[str, CompletionProvider] = {}

    def register(self, spec: ProviderSpec, impl: CompletionProvider) -> None:
        self._specs.append(spec)
        self._impls[spec.name] = impl

    def _candidates(self, max_tier: ProviderTier) -> list[ProviderSpec]:
        ceiling = _TIER_ORDER[max_tier]
        eligible = [s for s in self._specs if _TIER_ORDER[s.tier] <= ceiling]
        return sorted(eligible, key=lambda s: (_TIER_ORDER[s.tier], s.priority))

    def route(self, request: CompletionRequest) -> CompletionResult:
        attempted: list[str] = []
        reasons: list[str] = []

        for spec in self._candidates(request.max_tier):
            if not self._ledger.can_afford(request.account_id, spec.credit_weight):
                attempted.append(spec.name)
                reasons.append(f"insufficient credits (needs {spec.credit_weight})")
                continue

            impl = self._impls[spec.name]
            try:
                text = impl.complete(request.prompt)
            except ProviderError as exc:
                attempted.append(spec.name)
                reasons.append(exc.reason)
                continue

            self._ledger.charge(
                request.account_id,
                spec.credit_weight,
                reason=f"completion via {spec.name}",
            )
            return CompletionResult(
                text=text,
                served_by=spec.name,
                credits_charged=spec.credit_weight,
                attempts=list(attempted),
            )

        raise AllProvidersExhaustedError(attempted, reasons)
