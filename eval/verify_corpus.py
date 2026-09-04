"""Assert the rendered corpus contains exactly what the ledger declares.

The failure this exists to prevent: documents drifting away from eval/cases.json, so that
detection numbers are measured against a corpus which no longer contains the flaw we think
we planted. It is silent, it is not caught by any test of the engine, and it invalidates
every number downstream.

Four checks, in increasing order of what they buy:

1. SURFACE       every manifest surface string is verbatim in its document. Cheap, and it
                 catches a renderer that recorded one thing and wrote another.
2. COMPLETENESS  every date-like and money-like token in a document is accounted for by a
                 manifest entry. This is what makes absence provable: without it a manifest
                 says what the renderer meant to write, not what a reader would find.
3. AGREEMENT     the canonical values in the manifest disagree across documents in exactly
                 the places the ledger plants a CONTRADICTION, and nowhere else. This is
                 the check that proves the clean cases are actually clean.
4. NEAR MISSES   every near miss declared as surface_variation really is realised as two or
                 more different surface strings for one identical canonical value.

Registrations are deliberately not part of check 2. A regex permissive enough for
UP-32-DN-6647, UP32DN6647, U.P. 32 DN 6647 and DL-8C-AF-3092 is permissive enough to match
things that are not registrations, and a verifier with false positives gets disabled. They
are covered by check 4 instead, which needs no pattern.

Run:  python -m eval.verify_corpus
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases.json"
MANIFEST_DIR = ROOT / "eval" / "manifests"

FACT_TOKENS = [
    re.compile(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{4}\b"),          # 14/03/2026, 12.03.2026
    re.compile(r"\b\d{1,2}-[A-Za-z]{3}-\d{4}\b"),            # 04-Mar-2026
    re.compile(r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b"),        # 2 March 2026
    re.compile(r"\b[A-Z][a-z]+\s+\d{1,2},\s*\d{4}\b"),       # February 12, 2026
    re.compile(r"\b\d{1,3}(?:,\d{2})+,\d{3}\b"),             # 4,50,000
    re.compile(r"\b\d+\.\d{2}\b"),                           # 14200.00, and clock times
]


def flatten(text: str) -> str:
    """Collapse whitespace before substring matching.

    Documents wrap. A quote that is verbatim in the source can still span a line break, so a
    naive `in` test rejects a correct quote - which would make the phase 7 citation validator
    strip good citations. Normalise both sides and compare content, not layout.
    """
    return " ".join(text.split())


def canonical_by_document(manifest: dict) -> dict[str, dict[str, set[str]]]:
    """field -> doc_id -> set of canonical values recorded for it in that document."""
    table: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for doc_id, doc in manifest["documents"].items():
        for entry in doc["fields"]:
            table[entry["field"]][doc_id].add(entry["canonical"])
    return table


def main() -> int:
    errors: list[str] = []
    ledger = json.loads(CASES.read_text(encoding="utf-8"))
    live = [c for c in ledger["cases"] if c.get("status") != "placeholder"]

    checked_surfaces = 0
    checked_tokens = 0
    verified_near_misses = 0
    skipped_near_misses = 0

    for case in live:
        cid = case["case_id"]
        manifest_path = MANIFEST_DIR / f"{cid}.json"
        if not manifest_path.exists():
            errors.append(f"{cid}: no manifest at {manifest_path.relative_to(ROOT)}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if set(manifest["documents"]) != set(case["documents"]):
            errors.append(f"{cid}: manifest documents {sorted(manifest['documents'])} "
                          f"do not match ledger documents {sorted(case['documents'])}")

        texts: dict[str, str] = {}
        for doc_id, doc in manifest["documents"].items():
            path = ROOT / doc["path"]
            if not path.exists():
                errors.append(f"{cid}/{doc_id}: document missing at {doc['path']}")
                continue
            texts[doc_id] = flatten(path.read_text(encoding="utf-8"))

            # 1. SURFACE
            for entry in doc["fields"]:
                checked_surfaces += 1
                if flatten(entry["surface"]) not in texts[doc_id]:
                    errors.append(f"{cid}/{doc_id}: manifest claims {entry['surface']!r} for "
                                  f"{entry['field']} but it is not in the document")

            # 2. COMPLETENESS
            surfaces = " || ".join(flatten(e["surface"]) for e in doc["fields"])
            for pattern in FACT_TOKENS:
                for token in pattern.findall(texts[doc_id]):
                    checked_tokens += 1
                    if token not in surfaces:
                        errors.append(f"{cid}/{doc_id}: {token!r} looks like a fact but no "
                                      f"manifest entry accounts for it")

        # 3. AGREEMENT
        table = canonical_by_document(manifest)
        disagreeing = set()
        for field, per_doc in table.items():
            if len(per_doc) < 2:
                continue                                  # only one document mentions it
            if any(len(values) != 1 for values in per_doc.values()):
                continue                                  # repeated field, e.g. estimate lines
            if len({next(iter(v)) for v in per_doc.values()}) > 1:
                disagreeing.add(field)

        planted = {f["field"] for f in case["planted"] if f["klass"] == "CONTRADICTION"}
        for field in sorted(disagreeing - planted):
            values = {d: next(iter(v)) for d, v in table[field].items()}
            errors.append(f"{cid}: documents disagree about {field} ({values}) but the ledger "
                          f"plants no contradiction for it")
        for field in sorted(planted - disagreeing):
            errors.append(f"{cid}: ledger plants a contradiction on {field} but the rendered "
                          f"documents agree about it")

        # 4. NEAR MISSES
        for near in case["near_misses"]:
            if near.get("kind") != "surface_variation":
                skipped_near_misses += 1
                continue
            field = near["field"]
            per_doc = table.get(field, {})
            surfaces_seen = {
                e["surface"]
                for doc in manifest["documents"].values()
                for e in doc["fields"]
                if e["field"] == field
            }
            canonicals = {value for values in per_doc.values() for value in values}
            if len(surfaces_seen) < 2:
                errors.append(f"{cid}: near miss on {field} claims surface variation but only "
                              f"{len(surfaces_seen)} distinct surface was rendered")
            elif len(canonicals) != 1:
                errors.append(f"{cid}: near miss on {field} renders {len(canonicals)} different "
                              f"canonical values, so it is a contradiction and not a near miss")
            else:
                verified_near_misses += 1

    if errors:
        print(f"FAIL - {len(errors)} problem(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    documents = sum(len(json.loads((MANIFEST_DIR / f"{c['case_id']}.json").read_text(encoding='utf-8'))["documents"]) for c in live)
    print(f"OK - {documents} documents across {len(live)} cases")
    print(f"     {checked_surfaces} manifest surfaces found verbatim in their documents")
    print(f"     {checked_tokens} fact-shaped tokens scanned, all accounted for")
    print(f"     cross-document disagreements match the planted contradictions exactly")
    print(f"     {verified_near_misses} surface-variation near misses realised, "
          f"{skipped_near_misses} of other kinds not checkable from the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
