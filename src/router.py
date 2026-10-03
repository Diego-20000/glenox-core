"""Provider routing with account limits, fallback, credits and idempotency."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

from .credits import CreditLedger
from .exceptions import AllProvidersExhaustedError, ProviderError, UnknownAccountError
from .models import CompletionRequest, CompletionResult, ProviderSpec, ProviderTier
from .providers import CompletionProvider

_TIER_ORDER = {
    ProviderTier.FREE: 0,
    ProviderTier.STANDARD: 1,
    ProviderTier.PREMIUM: 2,
}


class CompletionRouter:
    def __init__(self, ledger: CreditLedger) -> None:
        self._ledger = ledger
        self._specs: list[ProviderSpec] = []
        self._impls: dict[str, CompletionProvider] = {}
        self._account_tiers: dict[str, ProviderTier] = {}
        self._account_locks: defaultdict[str, Lock] = defaultdict(Lock)
        self._idempotency_cache: dict[tuple[str, str], tuple[str, CompletionResult]] = {}

    def register_account(self, account_id: str, max_tier: ProviderTier) -> None:
        account_id = account_id.strip()
        if not account_id:
            raise ValueError("account_id must not be blank")
        self._account_tiers[account_id] = max_tier

    def register(self, spec: ProviderSpec, impl: CompletionProvider) -> None:
        if spec.name in self._impls:
            raise ValueError(f"provider already registered: {spec.name}")
        self._specs.append(spec)
        self._impls[spec.name] = impl

    def _candidates(self, max_tier: ProviderTier) -> list[ProviderSpec]:
        ceiling = _TIER_ORDER[max_tier]
        eligible = [spec for spec in self._specs if _TIER_ORDER[spec.tier] <= ceiling]
        return sorted(eligible, key=lambda spec: (_TIER_ORDER[spec.tier], spec.priority))

    def route(self, request: CompletionRequest) -> CompletionResult:
        max_tier = self._account_tiers.get(request.account_id)
        if max_tier is None:
            raise UnknownAccountError(request.account_id)

        with self._account_locks[request.account_id]:
            cache_key = None
            if request.request_id is not None:
                cache_key = (request.account_id, request.request_id)
                cached = self._idempotency_cache.get(cache_key)
                if cached is not None:
                    cached_prompt, cached_result = cached
                    if cached_prompt != request.prompt:
                        raise ValueError("request_id was already used with a different prompt")
                    return cached_result.model_copy(deep=True)

            attempted: list[str] = []
            reasons: list[str] = []

            for spec in self._candidates(max_tier):
                if not self._ledger.can_afford(request.account_id, spec.credit_weight):
                    attempted.append(spec.name)
                    reasons.append(f"insufficient credits (needs {spec.credit_weight})")
                    continue

                try:
                    response_text = self._impls[spec.name].complete(request.prompt)
                except ProviderError as exc:
                    attempted.append(spec.name)
                    reasons.append(exc.reason)
                    continue

                self._ledger.charge(
                    request.account_id,
                    spec.credit_weight,
                    reason=f"completion via {spec.name}",
                )
                result = CompletionResult(
                    request_id=request.request_id,
                    text=response_text,
                    served_by=spec.name,
                    credits_charged=spec.credit_weight,
                    attempts=list(attempted),
                )
                if cache_key is not None:
                    self._idempotency_cache[cache_key] = (request.prompt, result)
                return result

        raise AllProvidersExhaustedError(attempted, reasons)
