# PROMPTS.md — running Claude Code for this build

You are new to Claude Code, so this file is two things: a short orientation, then the
actual prompts to use, in order. Keep this file open in a second window during the hackathon.

Delete this file from the repo before submitting, or move it to `docs/` — it is scaffolding,
not part of the deliverable.

---

## Part 1 — Orientation (read once, 5 minutes)

**What it is.** You run `claude` in your project folder. It reads and writes files in that
folder, runs commands, and asks permission before doing anything destructive. It is not a
chat window that hands you code to paste — it edits the repo directly.

**The five things that matter most:**

1. **`CLAUDE.md` is auto-loaded every session.** It is the project's constitution. Anything
   the agent must never forget goes there. It is already written for you.

2. **Plan mode before big work.** Press `Shift+Tab` twice to enter plan mode. The agent
   researches and proposes a plan without touching files; you approve before it writes
   anything. Use it at the start of every numbered phase below. This is the single habit
   that separates good results from a mess.

3. **`/clear` between phases.** Context fills up and old context makes the agent worse, not
   better. When a phase is committed and done, `/clear` and start the next one fresh — the
   agent re-reads `CLAUDE.md` and `docs/SPEC.md` and is sharper for it. Do not run one
   24-hour conversation.

4. **`@` references files.** Typing `@docs/SPEC.md` pulls that file into context precisely.
   Better than describing what's in it.

5. **Git is your undo button.** Commit before anything risky. If a phase goes sideways,
   `git reset --hard` and re-prompt rather than asking the agent to untangle it — untangling
   costs more time than redoing.

**Two habits that will save you:**

- **Read the diffs.** Skim what it changed before you accept. You are responsible for this
  code in a demo; "the agent wrote it" is not an answer to a judge's question.
- **Never say "make it better."** Vague prompts produce vague sprawl. Every prompt below
  names a file, a behaviour and a done-condition.

**Two traps specific to this hackathon:**

- **Commit rhythm.** The rubric checks for real progression over 24 hours. An agent makes it
  easy to produce four giant commits. Commit at the end of every phase, minimum.
- **Judgement is yours.** The agent will happily build a competent, generic claims reviewer.
  The calibration section, the dismissed near-misses, the citation validator, the decision
  ordering, the README framing — those come from you, and those are what the "problem
  understanding and judgement" criterion scores.

---

## Part 2 — Setup, before the clock starts

```bash
mkdir nexustiq-ps02 && cd nexustiq-ps02
git init
# copy CLAUDE.md into the root, and SPEC.md into docs/
mkdir -p docs && cp /path/to/SPEC.md docs/
git add -A && git commit -m "chore: project constitution and spec"
claude
```

First message in the session:

> Read @CLAUDE.md and @docs/SPEC.md in full. Don't write any code yet. Tell me back, in
> your own words: what the deliverable is, the three finding classes and how they differ,
> why contradiction detection must not use vector search, and what the decision ordering is
> and why it's ordered that way. If anything in the two documents contradicts itself or is
> underspecified, list it.

That last sentence matters. It surfaces gaps while they're cheap to fix.

---

## Part 3 — Phase prompts

Enter plan mode (`Shift+Tab` twice) for each of these. Approve the plan, let it build,
review the diff, commit, `/clear`.

### Phase 0 — Skeleton (target: 30 min)

> Build phase 0 from @docs/SPEC.md §10: the minimum runnable skeleton.
> `app.py` at the root starts a FastAPI app serving a static `index.html` on port 8000 with
> a health endpoint. `requirements.txt` pinned and minimal. `README.md` whose first line is
> exactly `TRACK_ID=PS02`. `.gitignore` covering venvs, `.env`, `__pycache__`.
> Create the `src/`, `data/`, `eval/`, `docs/` directories with `.gitkeep`.
> Verify it starts and responds, then stop. Do not build anything else.

Then, yourself: `python app.py`, open localhost:8000, confirm. Commit.

### Phase 1 — Policy and ledger (target: 90 min — **the most important phase**)

Do this one *with* the agent, not by delegating it. The ledger is your design thinking.

> Using @docs/SPEC.md §6, draft `data/policy/motor_policy.md`: a small motor insurance
> policy for private two-wheelers and cars covering own-damage and theft. Every clause gets
> a stable id `C-01`, `C-02`… Include IDV, claim windows, required documents by claim type,
> the exclusions listed in the spec, the deductible clause with a range by vehicle class,
> and a repair-relevance condition. Keep it tight — one page of real clauses, no filler.
> Also emit `data/policy/clauses.json`: id, title, type (coverage/exclusion/condition/window),
> text, and a machine-checkable predicate where one exists.

Review the policy yourself, line by line. Then:

> Now draft `eval/cases.json` following the schema in @docs/SPEC.md §7, for the ten cases in
> the table there. For each case declare: claim_type, expected_recommendation, planted
> findings with their consequence and expected citations, and near_misses marked
> `must_not_flag`. Do not write any claim documents yet — ledger only.
> Leave C10 as a placeholder with a note that it is written after code freeze.

**Read every line of the ledger and edit it yourself.** This is where your judgement enters
the project. Commit.

### Phase 2 — Claim documents (target: 60 min)

> Render the claim packets into `data/claims/<case_id>/` from `@eval/cases.json`. Each case
> gets a claim form, an FIR or repair estimate as appropriate to the case, and a customer
> incident narrative — as markdown/text, never PDF.
> Each document must contain exactly the planted findings declared for its case and no
> others. Apply the realism requirements in @docs/SPEC.md §7: varied date formats, varied
> currency formats, inconsistent field labels and capitalisation, officialese in the FIR, a
> rambling customer narrative that buries the date.
> Then write `eval/verify_corpus.py` that re-reads the generated documents and asserts each
> declared planted finding is actually present and each clean case is actually clean. Run it.

That verification script is not optional. It catches the corpus drifting from the ledger,
which is the failure mode that quietly ruins this whole approach.

Read a couple of the documents yourself. If they feel like an LLM wrote them, say so and
ask for another pass. Commit.

### Phase 3 — Extraction (target: 2 h)

> Build phase 3. `src/llm/gemini.py` is the only module that touches the Gemini API: it owns
> the model constants (overridable by env), retries with backoff, timeouts, structured-output
> JSON parsing and the failure fallback described in @CLAUDE.md §3.7.
> `src/extract/` turns one document into `list[ExtractedField]` per the schema in
> @docs/SPEC.md §4 — every field carries `doc_id` and an `exact_quote` that is a verbatim
> substring of the source. Add a check that rejects any extraction whose `exact_quote` is not
> found in the source text, and marks that field low-confidence instead of trusting it.
> Prompts live in `src/prompts/` as files.
> Add a CLI: `python -m src.extract.cli C04` printing the extracted fields.

### Phase 4 — Normalise and reconcile (target: 2.5 h) — **the core**

> Build phase 4. `src/normalise/` handles dates, Indian currency formats (`₹1,20,000`,
> `Rs. 1.2 lakh`, `120000`), vehicle registrations (`MH-12-AB-1234` == `MH12AB1234`), and
> field-label aliasing.
> `src/reconcile/` builds the reconciliation matrix: for every field name present in more
> than one document, compare normalised values across documents.
> This engine must be **generic** — driven by field names and comparators, with no branch
> that exists to catch a specific case. A difference that survives normalisation becomes a
> CONTRADICTION finding with citations to both documents; a difference that normalisation
> resolves becomes a DismissedObservation with the reason.
> Then run it over every case in the ledger and show me a table of what was found versus
> what was planted.

When you review this, the question to ask yourself: **would this catch a contradiction I
never thought of?** If the answer is no, it is not generic enough. Push back on the agent.

### Phase 5 — Policy engine (target: 2 h)

> Build phase 5. `src/policy/` runs the deterministic checks: claim window arithmetic, IDV
> cap, exclusion predicates, repair-relevance. Plus clause retrieval: embed
> `data/policy/clauses.json` with `gemini-embedding-001` at startup, precompute and commit
> the index, retrieve top-k candidate clauses per extracted fact and per repair line item,
> and have the model judge applicability with the clause text quoted in the prompt — it
> returns applicable/not with the clause id, never free text.
> Output POLICY_DEVIATION findings with clause citations.
> Confirm startup with index load stays well under 90 seconds.

### Phase 6 — Completeness and decision (target: 1 h)

> Build phase 6. `src/completeness/` checks required documents and required fields per claim
> type and emits INCOMPLETENESS findings — absence is a finding, reported explicitly.
> `src/decision.py` implements exactly the ordering in @docs/SPEC.md §5 as one pure function
> over the findings list, with a docstring explaining why incompleteness and contradictions
> are checked before policy rejection. No LLM call in this module.
> Run the full ledger and show expected vs actual recommendation per case.

At this point the engine is done and every case should land on its expected recommendation.
Do not proceed until it does. Commit.

### Phase 7 — Narrate and validate (target: 1.5 h)

> Build phase 7. `src/narrate/` sends the evidence bundle — findings, citations, dismissed
> observations, recommendation — to Gemini and gets prose back. It must never receive the
> raw documents and never be asked what the outcome should be.
> Then `src/validate/citations.py`: every quoted string and every doc/clause id in the
> narrative must exist verbatim in the bundle. Unverifiable content is stripped and the
> narrative regenerated once; if it fails again, fall back to the deterministic summary.
> Log validator statistics so we can report them in the README.

### Phase 8 — UI (target: 3 h)

> Build phase 8 per @docs/SPEC.md §9 — plain HTML/CSS/JS in `frontend/`, served statically
> by `app.py`, no build step.
> Case picker; the reconciliation matrix with conflicting cells highlighted; findings grouped
> by class and expandable to the exact quote and clause text; a "considered and dismissed"
> section; the recommendation with the rule that produced it in plain language and an explicit
> "for investigator review — the system does not approve claims" line.
> And the live-edit panel: let the user edit a field value on any document and re-run the
> review, so a finding visibly appears and disappears. That panel is the most important thing
> on the page — build it properly, not as an afterthought.

### Phase 9 — Eval harness (target: 45 min)

> Build `eval/run.py` per @docs/SPEC.md §8: run every ledger case and report false-alarm rate
> on clean cases, detection rate on planted findings, citation validity percentage, and
> near-miss suppression. Print a table and write `eval/results.md`.
> Assert that nothing under `src/` or `app.py` imports anything from `eval/`.

### Phase 10 — Hardening (target: 1.5 h)

> Harden per @CLAUDE.md §3.7 and §6. Simulate Gemini failures — timeout, malformed JSON, 429,
> empty response — and confirm the app degrades to the deterministic report without a 500.
> Confirm any single request completes within 60 seconds and startup within 90.
> Then walk me through a fresh-clone test: clone to a new directory, fresh venv, Python 3.11,
> `pip install -r requirements.txt`, `python app.py`, hit port 8000. Report anything that
> only works because of state in the original directory.

Run the fresh-clone test yourself as well. This is the most common way hackathon
submissions score zero, and it is entirely preventable.

### Phase 11 — Held-out case

Write C10 yourself, or with the agent in a fresh session that has not seen the detection
code. Run it. **Record the result honestly, including if it fails** — a caught-honest miss
plus an explanation of why beats a suspiciously perfect run.

### Phase 12 — README and video

Draft the README yourself. Use the agent to check completeness, not to write the framing.

> Review @README.md against the evaluation criteria and submission rules in the hackathon
> brief. Tell me what a judge would find missing or unverifiable. Do not rewrite it.

README must contain, after the `TRACK_ID=PS02` line: what it does; how to run it; the
architecture split between deterministic logic and LLM (a diagram is worth it); what data and
documents were generated and how; the eval numbers; the decision-ordering rationale; known
limitations stated plainly; and the demo video link.

**Video running order** (3 minutes tight): a clean case returning clean → the contradiction
case where the date conflict changes the window outcome → open the dismissed section and
show a near-miss that was correctly *not* flagged → the live-edit panel, change the date,
watch the finding vanish → one line on the citation validator → the eval numbers.

Lead with the clean case. Everyone else opens with a catch.

---

## Part 4 — When it goes wrong

- **Agent is sprawling / editing files you didn't expect** — stop it, `/clear`, re-prompt with
  a narrower scope naming exact files.
- **A phase produced a mess** — `git reset --hard HEAD` and re-prompt. Do not debug agent
  sprawl by hand; it costs more than redoing.
- **It special-cased a test case** — this is the most likely quality failure. Grep for case
  ids in `src/`. There should be none.
- **Behind schedule** — cut in this order: the extra ledger cases, then narrative polish,
  then UI styling. **Never cut** the live-edit panel, the dismissed section, the citation
  validator, or the fresh-clone test. Those are the score.
