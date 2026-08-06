"""glenox-core: a multi-provider completion router with fallback and
credit-based cost governance.

Public API surface — everything else in this package is an implementation
detail.
"""

from .credits import CreditLedger
from .exceptions import (
    AllProvidersExhaustedError,
    GlenoxCoreError,
    InsufficientCreditsError,
    ProviderError,
)
from .models import CompletionRequest, CompletionResult, CreditLedgerEntry, ProviderSpec, ProviderTier
from .providers import AlwaysFailsProvider, CompletionProvider, EchoProvider, UnreliableProvider
from .router import CompletionRouter

__version__ = "0.1.0"

__all__ = [
    "CompletionRouter",
    "CreditLedger",
    "CompletionRequest",
    "CompletionResult",
    "CreditLedgerEntry",
    "ProviderSpec",
    "ProviderTier",
    "CompletionProvider",
    "EchoProvider",
    "UnreliableProvider",
    "AlwaysFailsProvider",
    "GlenoxCoreError",
    "AllProvidersExhaustedError",
    "InsufficientCreditsError",
    "ProviderError",
]
