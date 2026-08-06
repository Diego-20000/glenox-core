"""Typed data contracts for the multi-provider completion engine.

The numbers here (weights, credit balances) are illustrative — the point
of this module is the *shape* of the contract (a provider has a name, a
tier, and a cost weight; a request carries an account and a tier ceiling),
not any real pricing.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProviderTier(str, Enum):
    """Providers are grouped into tiers so an account's plan determines
    which tiers it's allowed to draw from — a free-tier account never
    silently incurs a premium-tier cost."""

    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"


class ProviderSpec(BaseModel):
    """Static configuration for one completion provider."""

    name: str
    tier: ProviderTier
    credit_weight: int = Field(gt=0, description="Credits consumed per successful call.")
    priority: int = Field(description="Lower runs first within its tier.")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("provider name must not be blank")
        return v


class CompletionRequest(BaseModel):
    """A single inbound request to route to some provider."""

    account_id: str
    prompt: str
    max_tier: ProviderTier = ProviderTier.PREMIUM

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be blank")
        return v


class CompletionResult(BaseModel):
    """What the router returns on success: the answer plus which
    provider actually served it and what it cost, for auditability."""

    text: str
    served_by: str
    credits_charged: int
    attempts: list[str] = Field(default_factory=list, description="Providers tried before this one, in order.")


class CreditLedgerEntry(BaseModel):
    """One row in an append-only ledger — balances are always derived by
    summing entries, never mutated in place, so a balance can always be
    reconstructed and audited from history alone."""

    account_id: str
    delta: int
    reason: str
