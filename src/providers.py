"""Provider interface and reference implementations.

`CompletionProvider` is deliberately tiny — one method, one failure mode
(`ProviderError`) — so the router never needs to know which vendor it's
talking to. Swapping or adding a real vendor integration means writing
one class that implements `complete()`; nothing else in the engine
changes.

The implementations below are illustrative stand-ins (deterministic,
no network calls, no API keys) so the whole engine is runnable and
testable without any external service or credential.
"""

from __future__ import annotations

from typing import Protocol

from .exceptions import ProviderError


class CompletionProvider(Protocol):
    """Anything that can turn a prompt into text, or raise ProviderError
    trying. No other contract — no shared base class, no vendor SDK leaking
    into the router's type signature."""

    def complete(self, prompt: str) -> str: ...


class EchoProvider:
    """A trivial always-succeeds provider — stands in for a cheap, fast,
    free-tier model in examples and tests."""

    def __init__(self, name: str = "echo") -> None:
        self.name = name

    def complete(self, prompt: str) -> str:
        return f"[{self.name}] {prompt[::-1]}"


class UnreliableProvider:
    """Fails deterministically the first N calls, then succeeds — stands
    in for a real provider that occasionally times out or rate-limits,
    so the fallback chain has something real to fall back *from*."""

    def __init__(self, name: str, fail_times: int) -> None:
        self.name = name
        self._remaining_failures = fail_times

    def complete(self, prompt: str) -> str:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise ProviderError(self.name, "simulated timeout")
        return f"[{self.name}] {prompt.upper()}"


class AlwaysFailsProvider:
    """Stands in for a provider that's fully down (bad credentials,
    outage) — every call raises."""

    def __init__(self, name: str) -> None:
        self.name = name

    def complete(self, prompt: str) -> str:
        raise ProviderError(self.name, "simulated outage")
