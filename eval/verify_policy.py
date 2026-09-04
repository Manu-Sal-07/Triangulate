"""Assert that motor_policy.md and clauses.json say the same thing.

clauses.json duplicates the policy text so that findings can cite clause text without
re-parsing markdown at request time. Duplication drifts. This asserts it has not, and
also asserts the architecture rules from docs/DECISIONS.md ADR-001 that are expressible
as properties of the clause file:

  - a semantic clause may never be blocking (the model can raise a concern, not deny)
  - every machine clause names a checker from the known set
  - clause ids are unique and well formed, because findings cite them

Run:  python -m eval.verify_policy
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_MD = ROOT / "data" / "policy" / "motor_policy.md"
CLAUSES_JSON = ROOT / "data" / "policy" / "clauses.json"

HEADING = re.compile(r"^### (C-\d{2}) . (.+)$")

KNOWN_CHECKERS = {
    "time_window",
    "date_order",
    "amount_cap",
    "document_checklist",
    "range_lookup",
}
EVALUATIONS = {"machine", "semantic", "definitional"}
SEVERITIES = {"blocking", "material", "informational"}
FINDING_CLASSES = {"CONTRADICTION", "POLICY_DEVIATION", "INCOMPLETENESS"}


def collapse(text: str) -> str:
    """Whitespace-insensitive comparison: markdown wraps, JSON does not."""
    return " ".join(text.split())


def parse_markdown(path: Path) -> dict[str, tuple[str, str]]:
    """clause id -> (title, body). Body is everything up to the next heading."""
    clauses: dict[str, tuple[str, str]] = {}
    current: str | None = None
    title = ""
    body: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if match:
            if current:
                clauses[current] = (title, collapse(" ".join(body)))
            current, title = match.group(1), match.group(2).strip()
            body = []
        elif line.startswith("#") or line.startswith("---"):
            if current:
                clauses[current] = (title, collapse(" ".join(body)))
                current = None
            body = []
        elif current:
            body.append(line)

    if current:
        clauses[current] = (title, collapse(" ".join(body)))
    return clauses


def main() -> int:
    errors: list[str] = []
    md = parse_markdown(POLICY_MD)
    data = json.loads(CLAUSES_JSON.read_text(encoding="utf-8"))
    clauses = data["clauses"]

    ids = [c["id"] for c in clauses]
    if len(ids) != len(set(ids)):
        errors.append("duplicate clause ids in clauses.json")

    for missing in sorted(set(md) - set(ids)):
        errors.append(f"{missing}: in motor_policy.md but not in clauses.json")
    for missing in sorted(set(ids) - set(md)):
        errors.append(f"{missing}: in clauses.json but not in motor_policy.md")

    for clause in clauses:
        cid = clause["id"]
        if cid not in md:
            continue
        md_title, md_body = md[cid]

        if clause["title"] != md_title:
            errors.append(f"{cid}: title differs - json {clause['title']!r} vs md {md_title!r}")
        if collapse(clause["text"]) != md_body:
            errors.append(f"{cid}: clause text differs between clauses.json and motor_policy.md")

        evaluation = clause["evaluation"]
        if evaluation not in EVALUATIONS:
            errors.append(f"{cid}: unknown evaluation {evaluation!r}")

        if evaluation == "machine":
            check = clause.get("check")
            if not check:
                errors.append(f"{cid}: machine clause has no check")
            elif check["name"] not in KNOWN_CHECKERS:
                errors.append(f"{cid}: unknown checker {check['name']!r}")
            if clause.get("severity_on_fail") not in SEVERITIES:
                errors.append(f"{cid}: machine clause needs a valid severity_on_fail")

        elif evaluation == "semantic":
            if not clause.get("question"):
                errors.append(f"{cid}: semantic clause has no question for the model")
            # ADR-001: a model proposal can raise a concern, never deny a claim.
            if clause.get("max_severity") != "material":
                errors.append(f"{cid}: semantic clause must cap at material, not {clause.get('max_severity')!r}")
            if "check" in clause:
                errors.append(f"{cid}: semantic clause must not carry a deterministic check")

        elif evaluation == "definitional":
            if "check" in clause or "question" in clause:
                errors.append(f"{cid}: definitional clause carries a check or question")

        if evaluation != "definitional" and clause.get("finding_class") not in FINDING_CLASSES:
            errors.append(f"{cid}: invalid finding_class {clause.get('finding_class')!r}")

    counts = {e: sum(1 for c in clauses if c["evaluation"] == e) for e in sorted(EVALUATIONS)}
    checkers = sorted({c["check"]["name"] for c in clauses if "check" in c})

    if errors:
        print(f"FAIL - {len(errors)} problem(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK - {len(clauses)} clauses consistent between motor_policy.md and clauses.json")
    print(f"     {counts}")
    print(f"     {len(checkers)} checkers cover {counts['machine']} machine clauses: {', '.join(checkers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
