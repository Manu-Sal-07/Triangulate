# SPEC — PS02 Claims Evidence Review Assistant

The design reference. `CLAUDE.md` holds the rules; this holds the *what and why*.
Read this before implementing a phase.

---

## 1. Problem, in our own words

A motor insurance claims investigator spends their day assembling evidence before any
decision can be made. The documents rarely agree with each other, and the disagreements
are what matter. The job is not to decide the claim — it is to **assemble the evidence,
surface the conflicts, and hand a defensible position to a human**.

So the system's output is not a verdict. It is a **review**: what was submitted, what is
missing, where the documents disagree, which clauses apply, and what the investigator
should do next — every statement traceable to a document or a clause.

Design consequences we commit to:

- **Contradictions are surfaced, never smoothed over.** If two documents disagree, that
  disagreement is the headline, not a footnote.
- **Uncertainty escalates.** An unresolved contradiction produces `ESCALATE`, never a guess.
- **Silence is a finding.** A missing required document or an absent required clause is
  reported explicitly.
- **A clean claim comes back clean.** No findings, no manufactured concerns.
- **The system flags and explains; the human decides.** Our recommendation is a
  recommendation, and the UI says so.

---

## 2. Pipeline

```
claim packet (3 documents, markdown/text)
        |
   [1] EXTRACT          LLM, structured output, one call per document
        |               -> typed fields, each {value, doc_id, exact_quote}
        v
   [2] NORMALISE        pure Python
        |               dates, currency, vehicle reg, names, doc types
        v
   [3] RECONCILE        pure Python — generic field-vs-field across documents
        |               -> CONTRADICTION findings + dismissed near-misses
        v
   [4] POLICY ENGINE    pure Python (deterministic checks)
        |               + clause retrieval via gemini-embedding-001 for applicability
        |               -> POLICY_DEVIATION findings
        v
   [5] COMPLETENESS     pure Python — required docs/fields checklist
        |               -> INCOMPLETENESS findings
        v
   [6] DECISION         pure Python — a total function over findings
        |               -> APPROVE | APPROVE_CAPPED | REJECT | REQUEST_INFO | ESCALATE
        v
   [7] NARRATE          LLM, sees only the evidence bundle (never raw docs)
        |
        v
   [8] VALIDATE         pure Python — every quote & id must exist in the bundle
        |
        v
   ClaimReview (JSON) -> UI
```

Steps 2–6 and 8 are deterministic. Steps 1 and 7 are the only model calls.
This split is the single most important thing about the submission.

---

## 3. Where embeddings genuinely belong

Requirement: use `gemini-embedding-001`. We use it where it actually helps rather than
decoratively.

**Clause applicability retrieval.** Embed each policy clause once at startup (or
precompute and commit). For each extracted fact and each repair-estimate line item, retrieve
the top-k candidate clauses, then have the model judge applicability **with the clause text
quoted in the prompt**. The retrieval narrows the search; the deterministic checks and the
citation validator keep it honest.

We do **not** use embeddings to find contradictions. See CLAUDE.md §3.3.

---

## 4. Domain objects

```python
ExtractedField:
    name: str            # "incident_date", "vehicle_reg", "claim_amount"
    value: Any           # normalised
    raw: str             # as it appeared
    doc_id: str          # "CLAIM_FORM" | "FIR" | "REPAIR_ESTIMATE" | "CUSTOMER_NARRATIVE"
    exact_quote: str     # verbatim substring of the source document
    confidence: str      # "high" | "low" | "absent"

Finding:
    id: str
    klass: str           # CONTRADICTION | POLICY_DEVIATION | INCOMPLETENESS
    severity: str        # blocking | material | informational
    field: str | None
    summary: str         # one deterministic sentence, generated in Python
    citations: list[Citation]      # doc_id + quote, and/or clause_id + clause text
    consequence: str     # what it changes about the recommendation

DismissedObservation:            # the "considered and not flagged" section
    field: str
    what_differed: str           # "MH-12-AB-1234 vs MH12AB1234"
    why_dismissed: str           # "same registration after normalisation"

ClaimReview:
    claim_id: str
    recommendation: str          # see decision policy
    findings: list[Finding]
    dismissed: list[DismissedObservation]
    completeness: dict           # required doc -> present/absent
    narrative: str               # LLM, validated
    unresolved: list[str]        # what remains unknown
```

---

## 5. Decision policy (deterministic, in priority order)

1. The clause-applicability judge is advisory, and the split is by clause type — not by confidence.

Don't make this a judgement call at runtime. Partition the clauses when you build clauses.json:

Machine-checkable clauses — intimation windows, FIR deadlines, the IDV cap, required-document lists, deductible ranges. These are evaluated entirely in code. The model is never consulted about them. These are the only clauses permitted to produce a blocking finding.

Semantic clauses — commercial use of a private vehicle, driving under the influence, unauthorised repair before survey, repair-relevance. These genuinely need language understanding, so the model proposes with a mandatory verbatim quote from the document, returning {clause_id, applies: yes|no|unclear, quote, confidence}.

The rule that falls out: a model-proposed clause application can never by itself produce a rejection. It caps at material, which routes to ESCALATE. unclear, low confidence, or a quote that fails the citation validator discards the proposal entirely rather than downgrading it. One line for the README: the model can raise a concern; it cannot deny a claim.

One trap to close now: deterministic checks must not depend on retrieval. The intimation-window check runs on every claim whether or not the window clause was in the top-k. If retrieval gates your checks, a retrieval miss silently drops a check and you'll never notice — that's the kind of bug that survives to the demo.

2. IDV excess is material, not blocking — with a ratio threshold that does real work.

Exceeding IDV isn't a defect in the claim. The policy states a cap, the arithmetic is unambiguous, and applying it is exactly the sort of thing that should be automated rather than escalated. So: material severity, resolved by APPROVE_CAPPED, and show the arithmetic in the report — claimed ₹X, payable capped at ₹Y per clause C-nn, difference ₹Z.

But a claim slightly over IDV and a claim at three times IDV are different events. The first is tax and rounding. The second means something in the packet is wrong — likely the estimate and the insured value are describing different vehicles. So: one configurable ratio (start at 1.5×), above which the excess stops being a cap and becomes a material finding in its own right, routing to ESCALATE. Document the ratio and say why it exists; an unexplained magic number is worse than none.

3)Informational findings approve. And that exposes a flaw in the ordering I gave you.

Escalating on purely informational findings is precisely the "finds suspicion everywhere" failure the brief warns about — you'd be spending an investigator's attention, which is the exact cost the problem statement opens with.

But don't add an APPROVE_WITH_NOTES enum value. The recommendation answers what should the investigator do, and the action is identical to APPROVE; a label meaning "approve, and also read the report" is noise, since they're reading the report anyway. Return APPROVE with the informational findings attached, and let the UI render "Approved — 2 notes for the file."

That also lets you delete the else -> ESCALATE catch-all from §5, which was quietly hiding a decision. Revised:

if any INCOMPLETENESS is blocking       -> REQUEST_INFO
elif any unresolved CONTRADICTION       -> ESCALATE
elif any POLICY_DEVIATION is blocking   -> REJECT
elif any finding is material            -> ESCALATE
elif claim_amount > insured_value       -> APPROVE_CAPPED
else                                    -> APPROVE

Note material moved above the IDV cap. If a claim both exceeds IDV and has a material finding, a human looks before any payout figure is computed — you don't quietly cap a claim whose facts are in dispute. That reordering also means the 1.5× rule from question 2 needs no special branch: it emits a material finding and the existing ordering carries it to ESCALATE.

Two definitional guards while you're in there. blocking means changes the recommendation on its own; material means a human must look before this proceeds; informational means worth recording, changes nothing. And informational must never become a dumping ground for things normalisation resolved — those belong in dismissed. If a near-miss leaks into findings as informational, your clean cases stop looking clean and you lose the calibration story that's carrying the demo.

Which sharpens the eval assertion: clean cases must return APPROVE with zero findings, with dismissed observations expected and allowed

---

## 6. Policy document — what it must contain

One motor policy, small and tight. Every clause gets a stable `clause_id` (`C-01`…) because
citations point at ids.

- Scope: private two-wheelers and cars; own-damage and theft.
- Insured Declared Value (IDV) per vehicle; claims capped at IDV.
- Claim windows: incident intimation within N hours; FIR within N days for theft;
  document submission within N days.
- Required documents by claim type (accident vs theft) — theft **requires** an FIR.
- Exclusions: driving without a valid licence; driving under the influence; private vehicle
  used commercially; wear-and-tear and consequential loss; unauthorised repairs before survey.
- Conditions: repair estimate must relate to the reported damage; deductible/excess amount.
- Deliberately include one clause with a **range** (e.g. deductible varies by vehicle class)
  so the engine must reason over a range rather than an equality.

---

## 7. Case ledger — ground truth first, documents second

**This is the method. Do not generate documents and then look for contradictions in them.**

Author `eval/cases.json` first, by hand. Each entry declares the planted findings and the
expected outcome. Then render the claim documents *from* that ledger.

```json
{
  "case_id": "C04",
  "claim_type": "accident",
  "expected_recommendation": "ESCALATE",
  "planted": [
    {
      "klass": "CONTRADICTION",
      "field": "incident_date",
      "detail": "claim form 2026-03-14 vs FIR 2026-03-12",
      "consequence": "crosses the 48h intimation window in C-07",
      "expected_citations": ["CLAIM_FORM", "FIR", "C-07"]
    }
  ],
  "near_misses": [
    {
      "field": "vehicle_reg",
      "what_differed": "MH-12-AB-1234 vs MH12AB1234",
      "must_not_flag": true
    }
  ]
}
```

Three things this buys us: the documents provably contain the flaw we think they do; we get
a labelled test set for free; and we can report real detection numbers in the README.

### Case set — 8 to 10 cases, roughly half clean

Clean cases matter *more* than dirty ones. They prove the system is not a
contradiction-generator. Most teams will plant a flaw in every case and unknowingly demo a
system that can only say "problem found."

| Case | Type     | Contains                                                                                             | Expected               |
| ---- | -------- | ---------------------------------------------------------------------------------------------------- | ---------------------- |
| C01  | accident | nothing wrong                                                                                        | APPROVE                |
| C02  | theft    | nothing wrong, FIR present and timely                                                                | APPROVE                |
| C03  | accident | clean but*superficially odd* — large claim, night-time incident, all legitimate                   | APPROVE                |
| C04  | accident | incident-date conflict that crosses the intimation window                                            | ESCALATE               |
| C05  | theft    | FIR missing entirely                                                                                 | REQUEST_INFO           |
| C06  | accident | estimate bills a rear bumper on a front-impact narrative                                             | ESCALATE               |
| C07  | accident | claim amount exceeds IDV                                                                             | APPROVE_CAPPED         |
| C08  | accident | hard exclusion — private vehicle in commercial use                                                  | REJECT                 |
| C09  | accident | clean, but near-misses everywhere (reg formatting, GST on estimate, FIR filed 2 days after incident) | APPROVE, all dismissed |
| C10  | theft    | written**after the code is frozen**, never used during development                             | held out               |

C03 and C09 are the cases that win the demo. C10 is the credibility case.

### Realism requirement

LLM-generated documents drift toward uniform, tidy prose, which flattens extraction into
something trivial and makes the corpus look synthetic. Deliberately vary:

- inconsistent capitalisation and abbreviations (`Regn No.`, `Reg. No`, `VEHICLE NO`)
- amounts written `₹1,20,000` / `120000` / `Rs. 1.2 lakh`
- dates as `14/03/2026`, `14-Mar-2026`, `March 14, 2026`
- a customer narrative that rambles, uses "approx", and buries the date mid-paragraph
- an FIR in officialese; a repair estimate as a line-item table with part codes

Messy-but-legitimate variation is what makes normalisation a real capability.

---

## 8. Evaluation, reported in the README

Run the whole ledger through the pipeline and report:

- **False-alarm rate on clean cases** — target zero findings on C01, C02, C03, C09.
- **Detection rate on planted findings** — per case, did we catch it and cite it correctly?
- **Citation validity** — % of quotes in the narrative that exist verbatim in the source.
- **Near-miss suppression** — every `must_not_flag` observation appears under *dismissed*,
  not under *findings*.

Ship this as `python -m eval.run` writing a small table. Numbers in the README beat
adjectives, and no other team will have them.

---

## 9. UI — what it must show

Judged in a 5-minute video, so the screen must make the reasoning visible.

1. **Case picker** — select one of the ledger cases, plus the live-edit panel below.
2. **Reconciliation matrix** — fields down the side, documents across the top, conflicting
   cells highlighted. This is the signature visual. Nothing else communicates the idea faster.
3. **Findings list** — grouped by class, each expandable to the exact quote and clause text.
4. **Considered and dismissed** — the near-misses, with the reason each was dismissed.
   Small section, disproportionate credibility.
5. **Recommendation** — with the rule that produced it stated in plain language, and an
   explicit "for investigator review — the system does not approve claims" line.
6. **Live edit panel** — let the judge change a field (e.g. the incident date on the claim
   form) and re-run. The finding appears and disappears in front of them. This single feature
   kills the "did you hardcode the demo?" question permanently. Build it.

---

## 10. Build order

Each phase ends in a commit and a working app. Never leave the app broken overnight.

| #  | Phase                   | Output                                                                              |
| -- | ----------------------- | ----------------------------------------------------------------------------------- |
| 0  | Skeleton                | `app.py` serving a page on :8000, `requirements.txt`, README with TRACK_ID line |
| 1  | Ledger                  | `eval/cases.json` hand-written; policy document with clause ids                   |
| 2  | Documents               | claim packets rendered from the ledger into`data/claims/`                         |
| 3  | Extraction              | Gemini structured output →`ExtractedField` with provenance                       |
| 4  | Normalise + reconcile   | the matrix; CONTRADICTION findings; dismissed near-misses                           |
| 5  | Policy engine           | deterministic checks + clause retrieval; POLICY_DEVIATION findings                  |
| 6  | Completeness + decision | INCOMPLETENESS findings; decision policy function                                   |
| 7  | Narrate + validate      | LLM narrative over the bundle; citation validator                                   |
| 8  | UI                      | matrix, findings, dismissed, recommendation, live-edit panel                        |
| 9  | Eval harness            | `python -m eval.run`, numbers into README                                         |
| 10 | Hardening               | Gemini-failure fallback, timeouts, fresh-clone test in a clean venv                 |
| 11 | Held-out case           | write C10, run it, record the result                                                |
| 12 | README + video          | framing written by hand, not generated                                              |

**Phases 0–7 must be done before the UI.** A beautiful UI over a weak engine loses to a plain
UI over a strong one, on this rubric specifically.

---

## 11. Open items to confirm with organisers

- The problem statement heads this track `TRACK_ID=PS02`, but the submission example shows
  `TRACK_ID=PS6` without a leading zero. The line is likely machine-read. Use the form from
  the track heading (`PS02`) and ask the organisers to confirm.
- Demo video length: the evaluation section says 2–3 minutes, the Devfolio submission line
  says 5 minutes. Prepare 3 minutes tight, with 2 minutes of extra depth available.
