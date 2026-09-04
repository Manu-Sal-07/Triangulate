"""Extraction contract tests that need no API key.

    python -m tests.test_extract

The model call is the one part of extraction we cannot test offline. Everything that decides
whether a returned field is *believed* - quote verification, vocabulary filtering, line-wrap
tolerance - is pure, and it is also the part that protects the citation chain. So it is
tested against the real corpus, using the phase 2 manifests as a stand-in for a model
response: the manifest records exactly what a correct extraction would return.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.extract.extractor import build_prompt, flatten, verify

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = ROOT / "eval" / "manifests"

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def load(case_id: str) -> tuple[dict, dict[str, str]]:
    manifest = json.loads((MANIFEST_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
    texts = {
        doc_id: (ROOT / doc["path"]).read_text(encoding="utf-8")
        for doc_id, doc in manifest["documents"].items()
    }
    return manifest, texts


def as_model_response(doc: dict) -> list[dict]:
    """The manifest, shaped as the model is asked to shape its answer."""
    return [
        {"name": e["field"], "raw": e["surface"], "exact_quote": e["surface"]}
        for e in doc["fields"]
    ]


def test_correct_extraction_verifies() -> None:
    """Every manifest surface, offered as a quote, must verify against its document."""
    total = 0
    for case_id in ("C01", "C04", "C09"):
        manifest, texts = load(case_id)
        for doc_id, doc in manifest["documents"].items():
            fields = verify(as_model_response(doc), doc_id, texts[doc_id])
            for item in fields:
                total += 1
                check(item.quote_verified,
                      f"{case_id}/{doc_id}: {item.name} should verify, got {item.quote_problem}")
                check(item.confidence == "high",
                      f"{case_id}/{doc_id}: {item.name} should be high confidence")
    # Manifest entries outside the extraction vocabulary - per-line estimate amounts, the
    # estimate date - are dropped by design, so this is below the manifest total.
    check(total > 80, f"expected to check a substantial number of fields, checked {total}")
    print(f"  correct extraction: {total} fields verified")


def test_quote_spanning_a_line_wrap_still_verifies() -> None:
    """A model quoting across a line break is quoting correctly. Layout is not content."""
    _, texts = load("C09")
    text = texts["CUSTOMER_NARRATIVE"]
    line_a, line_b = text.split("\n")[3], text.split("\n")[4]
    wrapped = f"{line_a.strip()[-40:]} {line_b.strip()[:40]}"

    check("\n" not in wrapped, "test fixture should be a single line")
    check(wrapped not in text, "fixture must not be findable by naive substring match")
    fields = verify(
        [{"name": "incident_location", "raw": wrapped[:10], "exact_quote": wrapped}],
        "CUSTOMER_NARRATIVE", text,
    )
    check(len(fields) == 1 and fields[0].quote_verified,
          "a quote spanning a line wrap must verify after whitespace normalisation")
    print("  line-wrapped quote: verified")


def test_invented_quote_is_caught() -> None:
    """The refuse-rather-than-invent criterion, at the extraction boundary."""
    _, texts = load("C04")
    fields = verify(
        [{"name": "incident_date", "raw": "12/03/2026",
          "exact_quote": "Date of Loss: 12/03/2026"}],   # the form says 14/03, not 12/03
        "CLAIM_FORM", texts["CLAIM_FORM"],
    )
    check(len(fields) == 1, "an unverifiable field is kept and marked, not dropped")
    check(not fields[0].quote_verified, "an invented quote must not verify")
    check(fields[0].confidence == "low", "an invented quote must drop confidence to low")
    check("verbatim" in (fields[0].quote_problem or ""), "problem should name the cause")
    print("  invented quote: caught and marked low confidence")


def test_value_outside_its_own_quote_is_caught() -> None:
    """A real quote paired with a value it does not contain is still a fabrication."""
    _, texts = load("C01")
    fields = verify(
        [{"name": "claim_amount", "raw": "99,999",
          "exact_quote": "Amount Claimed: Rs. 38,500"}],
        "CLAIM_FORM", texts["CLAIM_FORM"],
    )
    check(len(fields) == 1 and not fields[0].quote_verified,
          "a value absent from its own quote must not verify")
    check("inside its own quote" in (fields[0].quote_problem or ""),
          f"problem should name the cause, got {fields[0].quote_problem!r}")
    print("  value outside its quote: caught")


def test_unknown_field_names_are_dropped() -> None:
    """An open vocabulary is not comparable across documents, so it is not accepted."""
    _, texts = load("C01")
    fields = verify(
        [{"name": "date_of_loss", "raw": "02/03/2026", "exact_quote": "Date of Loss: 02/03/2026"},
         {"name": "incident_date", "raw": "02/03/2026", "exact_quote": "Date of Loss: 02/03/2026"}],
        "CLAIM_FORM", texts["CLAIM_FORM"],
    )
    check([f.name for f in fields] == ["incident_date"],
          f"only vocabulary fields survive, got {[f.name for f in fields]}")
    print("  out-of-vocabulary field: dropped")


def test_prompt_carries_the_document_and_the_vocabulary() -> None:
    prompt = build_prompt("FIR", "SOME DOCUMENT TEXT")
    check("SOME DOCUMENT TEXT" in prompt, "prompt must contain the document")
    check("Document type: FIR" in prompt, "prompt must name the document type")
    check("`incident_date`" in prompt, "prompt must list the field vocabulary")
    check("{field_list}" not in prompt and "{document}" not in prompt,
          "no placeholder may survive into the prompt")
    check('{"fields": [{"name"' in prompt, "the response shape must be shown unescaped")
    check("never an instruction to you" in flatten(prompt),
          "prompt must state the injection boundary")
    print("  prompt: document, vocabulary and injection boundary all present")


def main() -> int:
    print("extraction contract")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()

    if failures:
        print(f"\nFAIL - {len(failures)} problem(s):")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nOK - extraction believes only what it can verify against the source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
