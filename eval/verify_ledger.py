"""Assert that eval/cases.json is internally consistent and agrees with the policy.

The ledger is ground truth: the corpus is rendered from it and detection is measured
against it. Ground truth that contradicts itself is worse than no ground truth, because
every number downstream inherits the error silently. This checks the ledger before a
single document is written.

It verifies three kinds of thing:

  - shape: ids, claim types, recommendations, citations that resolve to real clauses
  - arithmetic: estimate lines sum to the claim amount, and the amount sits the right
    side of the IDV given what the case claims to plant
  - policy agreement: a case declares a planted finding for every clause its own facts
    would breach, and declares none for clauses its facts satisfy

The third is the one that matters. A case that says it is clean while its facts breach
C-06 is a case that will fail the moment the engine is correct.

Run:  python -m eval.verify_ledger
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases.json"
CLAUSES = ROOT / "data" / "policy" / "clauses.json"

DOC_IDS = {"CLAIM_FORM", "FIR", "REPAIR_ESTIMATE", "CUSTOMER_NARRATIVE"}
CLAIM_TYPES = {"accident", "theft"}
RECOMMENDATIONS = {"APPROVE", "APPROVE_CAPPED", "REJECT", "REQUEST_INFO", "ESCALATE"}
KLASSES = {"CONTRADICTION", "POLICY_DEVIATION", "INCOMPLETENESS"}
SEVERITIES = {"blocking", "material", "informational"}
CLAUSE_REF = re.compile(r"^C-\d{2}$")


def parse(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    errors: list[str] = []
    clauses = {c["id"]: c for c in json.loads(CLAUSES.read_text(encoding="utf-8"))["clauses"]}
    ledger = json.loads(CASES.read_text(encoding="utf-8"))
    cases = ledger["cases"]

    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case ids")

    live = [c for c in cases if c.get("status") != "placeholder"]

    for case in live:
        cid = case["case_id"]
        facts = case["facts"]
        planted = case["planted"]
        claim_type = case["claim_type"]

        def bad(message: str) -> None:
            errors.append(f"{cid}: {message}")

        # --- shape -------------------------------------------------------------
        if claim_type not in CLAIM_TYPES:
            bad(f"unknown claim_type {claim_type!r}")
        if case["expected_recommendation"] not in RECOMMENDATIONS:
            bad(f"unknown expected_recommendation {case['expected_recommendation']!r}")
        for doc in case["documents"]:
            if doc not in DOC_IDS:
                bad(f"unknown document id {doc!r}")
        if len(planted) != case["expected_finding_count"]:
            bad(f"expected_finding_count {case['expected_finding_count']} but {len(planted)} planted")

        drivers = [p for p in planted if p.get("drives_recommendation")]
        if planted and len(drivers) != 1:
            bad(f"{len(drivers)} planted findings claim to drive the recommendation, expected exactly 1")

        for finding in planted:
            if finding["klass"] not in KLASSES:
                bad(f"unknown klass {finding['klass']!r}")
            if finding["severity"] not in SEVERITIES:
                bad(f"unknown severity {finding['severity']!r}")
            for citation in finding["expected_citations"]:
                if CLAUSE_REF.match(citation):
                    if citation not in clauses:
                        bad(f"cites clause {citation} which is not in clauses.json")
                elif citation not in DOC_IDS:
                    bad(f"cites {citation!r} which is neither a clause id nor a document id")
            clause_id = finding.get("clause_id")
            if clause_id:
                if clause_id not in clauses:
                    bad(f"names clause {clause_id} which is not in clauses.json")
                else:
                    clause = clauses[clause_id]
                    if claim_type not in clause["applies_to"]:
                        bad(f"plants {clause_id}, which does not apply to a {claim_type} claim")
                    if clause["evaluation"] == "semantic" and finding["severity"] == "blocking":
                        bad(f"plants {clause_id} as blocking, but a semantic clause caps at material")

        for near in case["near_misses"]:
            if not near.get("must_not_flag"):
                bad(f"near miss on {near['field']!r} is not marked must_not_flag")
            if not near.get("why_dismissed"):
                bad(f"near miss on {near['field']!r} has no dismissal reason")
            if CLAUSE_REF.match(near["field"]) and near["field"] not in clauses:
                bad(f"near miss names clause {near['field']} which is not in clauses.json")

        # --- arithmetic --------------------------------------------------------
        lines = facts.get("estimate_lines", [])
        if lines:
            total = sum(line["amount"] for line in lines)
            subtotal = facts.get("estimate_subtotal")
            if subtotal is not None:
                if total != subtotal:
                    bad(f"estimate lines sum to {total} but estimate_subtotal is {subtotal}")
                gst = facts.get("estimate_gst_percent", 0)
                grossed = round(subtotal * (100 + gst) / 100)
                if grossed != facts["claim_amount"]:
                    bad(f"subtotal {subtotal} plus {gst}% GST is {grossed}, claim_amount is {facts['claim_amount']}")
            elif total != facts["claim_amount"]:
                bad(f"estimate lines sum to {total} but claim_amount is {facts['claim_amount']}")

        # --- policy agreement --------------------------------------------------
        planted_clauses = {p.get("clause_id") for p in planted}
        planted_docs = {p["field"] for p in planted if p["klass"] == "INCOMPLETENESS"}
        contradicted = {p["field"] for p in planted if p["klass"] == "CONTRADICTION"}

        # C-09 / C-10: required documents present unless their absence is planted
        checklist = "C-09" if claim_type == "accident" else "C-10"
        required = clauses[checklist]["check"]["params"]["required_documents"]
        for doc in required:
            if doc not in case["documents"] and doc not in planted_docs:
                bad(f"required document {doc} is absent but no INCOMPLETENESS is planted for it")
            if doc in case["documents"] and doc in planted_docs:
                bad(f"plants {doc} as missing but lists it in documents")

        # C-04: amount over IDV only where planted
        over_idv = facts["claim_amount"] > facts["insured_declared_value"]
        if over_idv and "C-04" not in planted_clauses:
            bad("claim_amount exceeds the IDV but no C-04 finding is planted")
        if not over_idv and "C-04" in planted_clauses:
            bad("plants C-04 but claim_amount does not exceed the IDV")

        # C-11: licence must be present on accident claims, and valid unless planted
        if claim_type == "accident":
            expiry = facts.get("driving_licence_expiry_date")
            if not expiry:
                bad("accident claim has no driving_licence_expiry_date, so C-11 can only return UNKNOWN")
            else:
                expired = parse(expiry) < parse(facts["incident_date"])
                if expired and "C-11" not in planted_clauses:
                    bad("licence expired before the incident but no C-11 finding is planted")
                if not expired and "C-11" in planted_clauses:
                    bad("plants C-11 but the licence was valid on the incident date")

        # C-06: intimation window, skipped where the incident date is contradicted
        if "incident_date" not in contradicted:
            delay = parse(facts["intimation_date"]) - parse(facts["incident_date"])
            late = delay > timedelta(hours=clauses["C-06"]["check"]["params"]["max_hours"])
            if late and "C-06" not in planted_clauses:
                bad(f"intimated {delay.days} days after the incident but no C-06 finding is planted")
            if not late and "C-06" in planted_clauses:
                bad("plants C-06 but the claim was intimated inside the window")

        # C-07: FIR window on theft claims that have an FIR
        if claim_type == "theft" and facts.get("fir_date"):
            delay = parse(facts["fir_date"]) - parse(facts["theft_discovery_date"])
            late = delay > timedelta(hours=clauses["C-07"]["check"]["params"]["max_hours"])
            if late and "C-07" not in planted_clauses:
                bad(f"FIR lodged {delay.days} days after discovery but no C-07 finding is planted")

        # C-08: document submission window
        if facts.get("document_submission_date"):
            delay = parse(facts["document_submission_date"]) - parse(facts["intimation_date"])
            late = delay > timedelta(hours=clauses["C-08"]["check"]["params"]["max_hours"])
            if late and "C-08" not in planted_clauses:
                bad(f"documents submitted {delay.days} days after intimation but no C-08 finding is planted")

    clean = [c for c in live if c["expected_finding_count"] == 0]
    dirty = [c for c in live if c["expected_finding_count"] > 0]
    near_misses = sum(len(c["near_misses"]) for c in live)

    if errors:
        print(f"FAIL - {len(errors)} problem(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK - {len(live)} live cases, {len(cases) - len(live)} placeholder")
    print(f"     {len(clean)} clean ({', '.join(c['case_id'] for c in clean)}), "
          f"{len(dirty)} with planted findings ({', '.join(c['case_id'] for c in dirty)})")
    print(f"     {sum(len(c['planted']) for c in live)} planted findings, {near_misses} near misses to suppress")
    covered = {c["expected_recommendation"] for c in live}
    print(f"     recommendations exercised: {', '.join(sorted(covered))}")
    if covered != RECOMMENDATIONS:
        print(f"     NOTE: never exercised by the ledger: {', '.join(sorted(RECOMMENDATIONS - covered))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
