"""Read one claim packet and print what was extracted.

    python -m src.extract.cli C04

Prints every field with its document, its raw value and the quote it came from, so the
provenance chain is inspectable without the UI.
"""

from __future__ import annotations

import asyncio
import sys

from src.extract.extractor import extract_packet, load_packet
from src.llm import gemini


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m src.extract.cli <CASE_ID>", file=sys.stderr)
        return 2

    case_id = argv[1].upper()
    try:
        documents = load_packet(case_id)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not gemini.available():
        print("GEMINI_API_KEY is not set - extraction will report failed for every document.")
        print("The app degrades this way on purpose; it does not crash.\n")

    results = asyncio.run(extract_packet(documents))

    total = 0
    for result in sorted(results, key=lambda r: r.doc_id):
        header = f"{result.doc_id}  [{result.status}]"
        print(f"\n{header}\n{'-' * len(header)}")
        if result.error:
            print(f"  ! {result.error}")
        for item in result.fields:
            total += 1
            flag = "" if item.quote_verified else f"  <-- {item.quote_problem}"
            print(f"  {item.name:<28} {item.raw!r}{flag}")
            print(f"  {'':<28} quote: {item.exact_quote.strip()[:96]!r}")

    print(f"\n{total} fields from {len(results)} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
