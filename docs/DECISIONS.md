# Architecture decision record

One entry per significant decision: the context that forced it, the decision, and the
consequences we accepted. Neutral and short. The reasoning behind the code, for anyone
reading the repository without having watched it get built.

Format: **Context** (what made a decision necessary) → **Decision** (what we chose) →
**Consequences** (what follows, including what we gave up).

---

## ADR-001 — Where authority sits: Python decides, the model describes

**Status:** accepted · **Date:** 2026-09-04 · **Affects:** `src/policy/`, `src/decision.py`,
`src/narrate/`, `data/policy/clauses.json`

### Context

The system must recommend an action on an insurance claim. A language model is capable of
reading the documents and answering "should this be approved?" directly, and that is the
shortest path to a working demo. It is also unaccountable: the answer cannot be traced to a
rule, it varies between runs on identical input, and it cannot be audited by the investigator
who has to defend the outcome. Insurance claim handling is a domain where the reasoning is
the product, not the verdict.

Separately, some policy clauses are arithmetic ("intimation within 48 hours", "capped at
IDV") while others require reading comprehension ("the vehicle was being used commercially").
Treating both kinds the same means either giving up on the semantic clauses or letting the
model's judgement reach the recommendation.

### Decision

Authority is split by *clause type*, decided when `clauses.json` is authored rather than at
runtime.

1. **Machine-checkable clauses** — intimation windows, FIR deadlines, the IDV cap,
   required-document lists, deductible ranges — are evaluated entirely in Python. The model
   is never consulted about them. These are the only clauses permitted to produce a
   `blocking` finding.
2. **Semantic clauses** — commercial use, driving under the influence, unauthorised repair
   before survey, repair-relevance — are *proposed* by the model, which must return
   `{clause_id, applies, quote, confidence}` with a verbatim quote from the document. A
   proposal that is `unclear`, low-confidence, or whose quote fails the citation validator is
   discarded outright rather than downgraded.
3. A model-proposed clause application caps at `material` severity, which routes to
   `ESCALATE`. **It can never by itself produce a rejection.**
4. **Deterministic checks never depend on retrieval.** The intimation-window check runs on
   every claim whether or not that clause appeared in the top-k retrieved candidates.

The recommendation itself is a pure function over the findings list, in this order:

```
blocking INCOMPLETENESS      -> REQUEST_INFO
unresolved CONTRADICTION     -> ESCALATE
blocking POLICY_DEVIATION    -> REJECT
any material finding         -> ESCALATE
claim_amount > insured_value -> APPROVE_CAPPED
otherwise                    -> APPROVE
```

Severity has fixed meanings: `blocking` changes the recommendation on its own; `material`
means a human must look before this proceeds; `informational` is worth recording and changes
nothing.

### Consequences

- **The model can raise a concern; it cannot deny a claim.** This is the sentence that
  summarises the architecture, and it is also a security property: with no path from document
  text to an outcome, an injected instruction in a claim document has nothing to steer.
- **Ordering is an epistemic claim, not a convenience.** Incompleteness and contradictions are
  resolved before the policy is applied, because applying a rule to evidence that is missing
  or self-contradictory means silently picking a winner between two documents.
- **`material` sits above the IDV cap** so a claim whose facts are in dispute is never quietly
  capped and paid; a human looks before any payout figure is computed.
- **Coupling to retrieval is deliberately weak.** If retrieval gated the deterministic checks,
  a retrieval miss would silently drop a check — a failure that produces no error and survives
  to the demo.
- **Cost:** semantic clauses can never produce a rejection even when the model is plainly
  right, so some true rejections will surface as `ESCALATE` instead. We accept the weaker
  outcome in exchange for never rejecting a claim on unaccountable grounds.
