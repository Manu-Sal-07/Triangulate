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

---

## ADR-002 — Policy rules are typed parameters dispatched to named checkers

**Status:** accepted · **Date:** 2026-09-05 · **Affects:** `data/policy/clauses.json`,
`src/policy/`, `eval/verify_policy.py`

### Context

Eight of the sixteen clauses in `motor_policy.md` are mechanically checkable: three time
windows, an IDV cap, a deductible that varies by vehicle class, two required-document lists,
and licence validity on the incident date. Something has to connect a clause id in a data file
to the code that evaluates it. Three shapes were considered:

1. **Prose only** — the clause text carries the rule; a hand-written Python function per clause
   hardcodes its numbers.
2. **Typed parameters** — the clause names a checker and supplies its parameters; the checker is
   written once per rule *shape*.
3. **An expression language** — the clause carries a predicate string such as
   `intimation_delay_hours <= 48`, parsed and evaluated at runtime.

Shape 1 makes every new clause a code change. Shape 3 is attractive because it appears to remove
per-clause code entirely.

### Decision

Shape 2. A machine-checkable clause carries `{"check": {"name": ..., "params": {...}}}`, and
checkers are written per rule shape rather than per clause. Five checkers — `time_window`,
`date_order`, `amount_cap`, `document_checklist`, `range_lookup` — cover all eight machine
clauses; C-06, C-07 and C-08 are three different windows sharing one function.

Every checker is a total function returning a triple, not a boolean:

```
CheckResult(status: PASS | FAIL | UNKNOWN, reason: str, inputs_used: list[FieldRef])
```

`eval/verify_policy.py` asserts that clause text in `clauses.json` still matches the
corresponding paragraph in `motor_policy.md`, and asserts ADR-001's rule as an executable
property of the data: no semantic clause may carry a severity above `material`.

### Consequences

- **Adding a clause of an existing shape is a data edit, not a code change** — the property that
  made shape 3 attractive, retained without its costs.
- **Checks can represent uncertainty, which an expression language cannot.** Inputs are extracted
  from documents, so a field may be absent or contradicted between two documents. A boolean
  predicate has two outcomes for a domain with three: coercing a missing intimation date to zero
  makes `0 <= 48` true and silently certifies that a claim with no date was intimated on time.
  `UNKNOWN` is what a window check must return when its input is missing (completeness reports
  it) or disputed (the contradiction escalates and the policy layer stays quiet). Emitting a
  cited `POLICY_DEVIATION` from a value that is actively in dispute would be worse than emitting
  nothing.
- **Findings build their own citations.** A checker declares the fields it read, so the citation
  list is generated rather than maintained by hand.
- **No runtime code evaluation.** Shape 3 would need `eval()` or a hand-written AST walker.
- **The rule parameters are duplicated** between the clause sentence and the params block. The
  text half is guarded by `verify_policy.py`; the numeric half is not, and is accepted at this
  policy size.
- **Not adopted, and why it would be at scale:** splitting each clause into a structural half and
  a narrative half, so that one clause can be checked both ways. It is the right shape for a large
  clause set, where most clauses carry both kinds of evidence. It needs two things this project
  does not: a cascade that runs the semantic half only where the deterministic half returned
  `UNKNOWN`, otherwise the escalation rate rises until triage stops being triage; and separate
  clause entries rather than two halves of one clause, so there is never a merge rule in which a
  model proposal overrides a deterministic pass.

---

## ADR-003 — The corpus is generated from the ledger and verified against a manifest

**Status:** accepted · **Date:** 2026-09-05 · **Affects:** `tools/render_corpus.py`,
`eval/verify_corpus.py`, `data/claims/`, `eval/manifests/`

### Context

Detection rates, false-alarm rates and near-miss suppression are all measured against the
claim corpus. If a document stops containing the flaw the ledger says it contains, every one
of those numbers is wrong and nothing reports an error. The corpus is generated, so this is
not hypothetical: any edit to the ledger, the templates or the prose can decouple them.

The obvious verification routes both fail. Checking the documents by eye does not scale past
the first edit. Checking them with the extraction pipeline is circular - the pipeline is the
thing under measurement, and at the time the corpus is authored it does not exist.

### Decision

The renderer is deterministic and emits its own oracle.

`tools/render_corpus.py` reads `eval/cases.json` and writes both the documents and, for each
case, a manifest recording every fact it wrote as `(field, canonical value, verbatim surface
string)`. It makes no model call and uses no randomness, so re-running produces byte-identical
output and version control itself becomes the drift detector.

`eval/verify_corpus.py` then asserts four properties:

1. every manifest surface string appears verbatim in its document;
2. every date-shaped and money-shaped token in a document is accounted for by a manifest
   entry;
3. the canonical values disagree across documents in exactly the places the ledger plants a
   `CONTRADICTION`, and nowhere else;
4. every near miss declared as surface variation renders two or more distinct surfaces for
   one identical canonical value.

Manifests are written to `eval/manifests/` rather than alongside the documents, because
CLAUDE.md 2.8 forbids the application from reading `eval/`.

### Consequences

- **Clean cases are provable, not assumed.** Property 1 alone proves only presence: a manifest
  records what the renderer meant to write, not what a reader would find. Property 2 closes
  the world, and closing the world is what makes absence checkable. C01, C02, C03 and C09
  carry the calibration argument, so this is the property that matters most.
- **Drift fails loudly in both directions.** An undeclared contradiction fails as hard as a
  planted one that went missing.
- **The app cannot cheat by construction.** Pre-extracted values live in the one directory the
  application is forbidden to read, rather than next to the documents where reading them would
  be a one-line accident.
- **Registrations are excluded from property 2 on purpose.** A pattern permissive enough for
  `UP-32-DN-6647`, `UP32DN6647`, `U.P. 32 DN 6647` and `DL-8C-AF-3092` also matches things that
  are not registrations, and a verifier that raises false alarms gets switched off. Property 4
  covers them without needing a pattern.
- **Quote matching is whitespace-normalised.** Two correct quotes initially failed because they
  spanned a line wrap. The phase 7 citation validator inherits this rule: compare content, not
  layout, or it will strip good citations.
- **Cost:** the narratives are hand-written, so an additional case costs prose rather than a
  configuration line. Accepted deliberately - that cost is what stops the corpus reading as
  machine-generated.
