# glenox-core

A small public reference project showing how an AI product can keep serving requests when a provider fails, while respecting account plans and usage budgets.

It is separate from the commercial Glenox application. Customer data, credentials, billing configuration and production integrations are intentionally outside this repository.

## The problem

A chatbot product backed by a single LLM provider has two failure modes
that show up the moment it has real traffic:

1. **The provider goes down or rate-limits you**, and every user gets an error at the worst possible moment.
2. **Every request costs the same to serve**, regardless of the account's
   plan or the query's complexity, so there's no way to offer a free
   tier without either subsidizing it into the ground or overengineering
   a separate cheap-and-nasty free product.

Glenox's answer to both: never talk to a provider directly. Route every
request through an engine that tries an *ordered chain* of providers —
cheapest and most permissive first — skips whatever the account can't
currently afford, and falls through automatically on failure. An account plan determines the ceiling of providers it can reach, instead of letting the request choose an unrestricted model.

## The architecture

```
CompletionRequest(account_id, prompt, request_id?)
              │
              ▼
     ┌─────────────────┐
     │  CompletionRouter │  walks providers ordered by
     │    (router.py)    │  (tier, priority), skipping
     └──────────┬────────┘  what the account can't afford
                │
     ┌──────────┴────────────────────────────┐
     │                                        │
     ▼                                        ▼
┌───────────┐                         ┌───────────────┐
│ CreditLedger │  balance = sum of    │ CompletionProvider │  one method:
│ (credits.py) │  every entry, ever — │   (providers.py)   │  complete(prompt)
│  append-only │  never mutated       │  one failure mode:  │  → str, or raises
└───────────┘  in place              │   ProviderError     │  ProviderError
                                      └───────────────┘
```

- **`src/providers.py`** — `CompletionProvider` is a `Protocol` with a
  single method. No shared base class, no vendor SDK types leaking into
  the router. Adding a real integration (Groq, Claude, whatever comes
  next) means writing one class with a `complete()` method; the router
  never changes.
- **`src/credits.py`** — the ledger is append-only. A balance is never a
  stored, mutated integer — it's always *derived* by summing every
  entry an account has. That makes a double-charge bug show up as a
  duplicate row in an inspectable history, instead of an untraceable
  off-by-one in some counter.
- **`src/router.py`** — the actual fallback loop: for each candidate
  provider (filtered by the account plan, ordered by tier then priority), check the account can afford it, try it, and on
  `ProviderError` move to the next one. Every attempt — including the
  failed ones — comes back on the result so a caller can see exactly
  what happened, not just who ultimately answered.
- **`src/models.py`** — Pydantic contracts for requests, results, and
  ledger entries. `credit_weight` must be positive, prompts can't be
  blank — invalid states fail at construction, not three call frames
  into the router.

## What is deliberately simplified

The credit weights, provider names and example plans are intentionally generic. They exist to make the fallback and budget rules easy to inspect. A production system would add persistent storage, real vendor adapters, secure credential handling, account administration and billing around this core.

## Running it

```bash
pip install -r requirements.txt
pip install -e .
pytest
```

```python
from src.credits import CreditLedger
from src.models import CompletionRequest, ProviderSpec, ProviderTier
from src.providers import EchoProvider, AlwaysFailsProvider
from src.router import CompletionRouter

ledger = CreditLedger()
router = CompletionRouter(ledger)
router.register_account("acct-1", max_tier=ProviderTier.STANDARD)
ledger.grant("acct-1", amount=10, reason="signup bonus")

router.register(
    ProviderSpec(name="primary", tier=ProviderTier.FREE, credit_weight=1, priority=0),
    AlwaysFailsProvider("primary"),  # simulates an outage
)
router.register(
    ProviderSpec(name="backup", tier=ProviderTier.FREE, credit_weight=2, priority=1),
    EchoProvider("backup"),
)

result = router.route(CompletionRequest(account_id="acct-1", prompt="hola"))
print(result.served_by)      # "backup"
print(result.attempts)       # ["primary"]
print(ledger.balance("acct-1"))  # 8
```

## License

MIT — see [LICENSE](LICENSE).


## What the example demonstrates

The sample keeps the important behavior visible without tying the project to a specific vendor:

- a plan sets the highest provider tier an account can use
- failed providers are skipped automatically
- a successful response is charged once
- repeated requests can carry an idempotency key
- usage remains inspectable through the credit ledger

That makes the repository useful as a compact architecture reference rather than a fake clone of a production vendor stack.
