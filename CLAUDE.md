# CLAUDE.md — Project Constitution

Read this before every task. If a request in the chat conflicts with a HARD RULE below,
stop and say so instead of complying.

Full design detail lives in `docs/SPEC.md`. Read it before implementing anything new.

---

## 1. What this is

NexusTiq24 hackathon submission, **TRACK_ID=PS02 — Insurance Claims Evidence Review Assistant**.

A motor-insurance claims investigator uploads/selects a claim packet (claim form, FIR or
repair estimate, customer incident description). The system reviews it against our motor
policy and produces a **claim review**: document completeness, cross-document
contradictions, applicable policy clauses, every finding cited to its source, and a
recommendation — approve / reject / request specific information / escalate.

Solo build, 24 hours. Judged on: working app, real commit history, sound engineering,
solving the actual problem including edge cases, well-grounded GenAI with citations,
and demonstrated judgement.

---

## 2. HARD RULES — never violate

1. **One command to run.** From repo root: `pip install -r requirements.txt`, then
   `python app.py` starts backend *and* frontend on **http://localhost:8000**.
   No second terminal. No build step at run time. No waiting for a keypress.
2. **Repo shape is fixed.** `app.py`, `requirements.txt`, `README.md` at the root.
   Everything else is our choice.
3. **README line 1 is exactly** `TRACK_ID=PS02` — nothing else on that line.
4. **Gemini is the only network call.** LLM and embeddings (`gemini-embedding-001`)
   via the Gemini API only. No other providers, no hosted vector DBs, no third-party
   RAG/memory services. FAISS / Chroma-local / numpy / sqlite are fine.
5. **Key comes from `GEMINI_API_KEY` env var.** Judges supply their own. Never commit a
   key, never read a key from a file, never hardcode one, never write one into an example.
6. **Never commit:** virtualenvs, `.env`, API keys, model weights, `__pycache__`, node_modules.
   **Always commit:** generated data, the built frontend, any precomputed index.
7. **Runtime limits.** Python 3.11 on a clean machine. `pip install` ≤ 10 min.
   App must answer on port 8000 within **90 seconds** of start. Any single request ≤ **60 seconds**.
   If embedding/indexing is slow, precompute it and commit the index.
8. **The app never reads `eval/`.** Ground truth is for measurement only. Any import of
   `eval/` from `src/` or `app.py` is a bug.

---

## 3. Architecture invariants — the thing being judged

These are not preferences. They are the reason this submission wins or loses.

### 3.1 Deterministic decisions, LLM narration
- **All findings and the final recommendation are produced by Python**, not by the model.
- The LLM has exactly two jobs: (a) **extract** document fields into a typed schema,
  (b) **write prose** over already-computed findings.
- The LLM never sees a raw document and is never asked "should this claim be approved?"
- Decision policy is a pure function of the findings list. It lives in one module and is readable
  end to end in under a screen.

### 3.2 Provenance on everything
- Every extracted field is `{value, doc_id, exact_quote}` — never a bare value.
- Every finding cites the document(s) and/or policy clause id it came from.
- A finding without a citation is a bug, not a warning.

### 3.3 Contradiction detection is a table comparison, never a vector search
- Vector retrieval returns the *most similar* passage, not the *conflicting* one.
  It structurally cannot find contradictions. Do not try.
- Instead: extract each document to a schema, then build a **reconciliation matrix** —
  the same normalised field laid side by side across all documents. Disagreement falls out
  of a generic comparison over field names.
- **The comparison engine is generic.** There must be no `if fir_date != form_date` branch,
  and no branch that exists to catch one specific planted case. One engine, many instances.

### 3.4 Normalise before comparing
`MH-12-AB-1234` and `MH12AB1234` are the same vehicle. `₹1,20,000`, `120000` and
`1.2 lakh` are the same amount. Dates arrive in several formats. Normalisation runs before
comparison, and a difference that survives normalisation is the only kind that gets flagged.
Near-misses that were normalised away are reported in the "considered and dismissed" section.

### 3.5 Three distinct finding classes — never collapse them
| Class | Meaning | Typical consequence |
|---|---|---|
| `CONTRADICTION` | Two documents disagree about the same fact | Escalate to investigator |
| `POLICY_DEVIATION` | A fact conflicts with a policy clause | Reject / cap / condition |
| `INCOMPLETENESS` | A required document or field is absent | Request that specific item |

Absence is a finding. A required clause or document that is simply missing must be
reported explicitly, never skipped silently.

### 3.6 Citation validator — the "refuse rather than invent" criterion, implemented
After the LLM writes the narrative, a validator programmatically checks that every quoted
string and every document/clause id it mentions exists verbatim in the evidence bundle.
Anything unverifiable is stripped or regenerated. This runs on every request and is
mentioned in the README and the demo video.

### 3.7 Graceful degradation
If the Gemini call fails, times out, or returns malformed JSON: retry once with backoff,
then fall back to the deterministic report with a plain-language note that the narrative
layer is unavailable. **The app never crashes and never returns a 500 to the user because
a model call failed.** Extraction failure on one document degrades to "could not extract —
escalated", not a stack trace.

---

## 4. Code conventions

- Backend Python. Frontend is our choice but **must be committed built** and served by `app.py`.
  Prefer plain HTML/CSS/JS served as static files — a React build step is risk we do not need.
- Modules under `src/`, each with one job. No file over ~300 lines. No god module.
- All LLM calls go through **one** client wrapper (`src/llm/gemini.py`) that owns retries,
  timeouts, JSON parsing and structured-output schemas. Nothing else calls the API directly.
- Model id and embedding model id are constants in **one** config module, overridable by env.
- Type hints on module boundaries. Dataclasses or Pydantic models for the domain objects
  (`ExtractedField`, `Finding`, `ClaimReview`) — no free-floating dicts across module boundaries.
- Prompts live in `src/prompts/` as files, not inline string soup.
- No cleverness. A judge reads this for four minutes. Obvious beats compact.

---

## 5. Commit discipline

The rubric explicitly checks for *"real progression across the 24 hours — not one giant
dump at the end."*

- Commit at every working milestone — target every **30–45 minutes**.
- One logical change per commit. Real messages: `feat: reconciliation matrix over normalised fields`,
  not `update` or `wip`.
- Never batch a session's work into one commit at the end.
- Commit before starting anything risky, so there is a known-good point to return to.

---

## 6. Definition of done for any feature

A feature is not done until:
1. It runs from a **fresh clone in a clean venv** — not just on this machine.
2. Startup stays under 90 s and a request under 60 s.
3. The clean claim case still returns **zero findings**. (Regressions here are the most
   damaging failure mode we have — a system that flags everything is worthless.)
4. Every new finding type it produces carries a citation.
5. It is committed with a meaningful message.

---

## 7. Do not

- Do not add a second run command, a build step, or a `Makefile` the judge must run.
- Do not add a dependency that is not needed. Every line of `requirements.txt` is install
  time we are spending against a 10-minute budget.
- Do not special-case a planted test case in application code.
- Do not let the model decide an outcome, invent a clause, or paraphrase a quote.
- Do not generate more sample data "for completeness" — a small, well-made set is
  explicitly what is being judged. Depth over volume.
- Do not write PDFs. Documents are markdown/text. OCR earns zero points.
- Do not refactor broadly without being asked; time is the scarcest resource here.
