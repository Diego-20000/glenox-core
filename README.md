# glenox-core

A reference implementation of the multi-provider LLM routing engine
behind **Glenox**, an AI chatbot product for small businesses built by
ArtPrograms Studio. Same idea as
[studio-analytics-core](https://github.com/Diego-20000/studio-analytics-core):
a distilled, open-source whitepaper of a real architectural decision,
reimplemented from scratch so it can be read and run by anyone —
without the proprietary business logic, pricing, or credentials that
live in the private product repo.

## The problem

A chatbot product backed by a single LLM provider has two failure modes
that show up the moment it has real traffic:

1. **The provider goes down or rate-limits you**, and every user gets an
   error, at the worst possible moment — mid-conversation.
2. **Every request costs the same to serve**, regardless of the account's
   plan or the query's complexity, so there's no way to offer a free
   tier without either subsidizing it into the ground or overengineering
   a separate cheap-and-nasty free product.

Glenox's answer to both: never talk to a provider directly. Route every
request through an engine that tries an *ordered chain* of providers —
cheapest and most permissive first — skips whatever the account can't
currently afford, and falls through automatically on failure. A
account's plan determines the ceiling of providers it can reach, not a
hardcoded model name anywhere in the request path.

## The architecture

```
CompletionRequest(account_id, prompt, max_tier)
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
  provider (filtered by the request's tier ceiling, ordered by tier
  then priority), check the account can afford it, try it, and on
  `ProviderError` move to the next one. Every attempt — including the
  failed ones — comes back on the result so a caller can see exactly
  what happened, not just who ultimately answered.
- **`src/models.py`** — Pydantic contracts for requests, results, and
  ledger entries. `credit_weight` must be positive, prompts can't be
  blank — invalid states fail at construction, not three call frames
  into the router.

## What's illustrative, not real

The credit weights, provider names, and tiers in the tests are example
values chosen to demonstrate the mechanism — not the real pricing or
provider lineup Glenox runs in production. The real product also layers
on things this reference implementation intentionally omits: real
vendor SDK integrations, WhatsApp/Gmail channel adapters, OAuth token
encryption at rest, MercadoPago billing, and account/plan management —
all proprietary, all left out here on purpose. What's here is the part
that best demonstrates the engineering: a provider-agnostic fallback
chain with auditable, credit-aware cost governance.

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
ledger.grant("acct-1", amount=10, reason="signup bonus")

router = CompletionRouter(ledger)
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
print(ledger.balance("acct-1"))  # 8 — only charged for the provider that answered
```

## License

MIT — see [LICENSE](LICENSE).
