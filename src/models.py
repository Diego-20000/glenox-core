"""Public data contracts for the routing engine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProviderTier(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"


class ProviderSpec(BaseModel):
    name: str
    tier: ProviderTier
    credit_weight: int = Field(gt=0, description="Credits consumed per successful call.")
    priority: int = Field(description="Lower runs first within its tier.")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("provider name must not be blank")
        return value


class CompletionRequest(BaseModel):
    account_id: str
    prompt: str
    request_id: str | None = None

    @field_validator("account_id", "prompt", "request_id")
    @classmethod
    def strings_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class CompletionResult(BaseModel):
    request_id: str | None
    text: str
    served_by: str
    credits_charged: int
    attempts: list[str] = Field(
        default_factory=list,
        description="Providers tried before success.",
    )


class CreditLedgerEntry(BaseModel):
    account_id: str
    delta: int
    reason: str

    @field_validator("account_id", "reason")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text field must not be blank")
        return value

    @field_validator("delta")
    @classmethod
    def delta_must_not_be_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("ledger delta must not be zero")
        return value
