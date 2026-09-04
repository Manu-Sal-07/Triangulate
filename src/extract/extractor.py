"""Turn one document into typed, provenance-carrying fields.

One document per call, deliberately. Putting the whole packet in one context would let the
model reconcile the documents itself: shown a claim form saying 14 March and an FIR saying
12 March, it returns one coherent date, the reconciliation matrix finds no disagreement, and
C04 approves. Nothing errors. Independence is a property that has to be engineered, and
shared context destroys it - so each document is read blind and Python does the comparing
(CLAUDE.md section 3.3).

Everything the model returns is checked before it is believed. A quote that is not verbatim
in the source does not make the field trustworthy, so the field survives marked low
confidence rather than being silently accepted.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from src import config
from src.extract.fields import BY_NAME, prompt_field_list, response_schema
from src.llm import gemini
from src.models import DocumentExtraction, ExtractedField

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_fields.md"

# Extraction is pure with respect to document text, so cache on the text itself rather than
# on a case id. A live edit to one field then re-extracts exactly that one document.
_CACHE: dict[str, DocumentExtraction] = {}


def flatten(text: str) -> str:
    """Collapse whitespace for quote matching.

    A quote can be verbatim in the source and still span a line wrap. Comparing layout
    instead of content would reject correct quotes, which is how a citation validator ends
    up stripping the good citations along with the invented ones.
    """
    return " ".join(text.split())


def _cache_key(doc_id: str, text: str) -> str:
    return f"{doc_id}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def build_prompt(doc_id: str, text: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{doc_id}", doc_id)
        .replace("{document}", text)
        .replace("{field_list}", prompt_field_list())
        .replace("{{", "{")
        .replace("}}", "}")
    )


def verify(items: list[dict], doc_id: str, text: str) -> list[ExtractedField]:
    """Check every returned field against the source before believing it."""
    haystack = flatten(text)
    fields: list[ExtractedField] = []

    for item in items:
        name = str(item.get("name", "")).strip()
        if name not in BY_NAME:
            continue                      # outside the vocabulary: not comparable, so drop it
        raw = str(item.get("raw", "")).strip()
        quote = str(item.get("exact_quote", "")).strip()
        if not raw or not quote:
            continue

        problem: str | None = None
        if flatten(quote) not in haystack:
            problem = "quote is not verbatim in the source document"
        elif flatten(raw) not in flatten(quote):
            problem = "value does not appear inside its own quote"

        fields.append(
            ExtractedField(
                name=name,
                raw=raw,
                doc_id=doc_id,
                exact_quote=quote,
                confidence="high" if problem is None else "low",
                quote_verified=problem is None,
                quote_problem=problem,
            )
        )
    return fields


def _result(doc_id: str, text: str, payload: object) -> DocumentExtraction:
    items = payload.get("fields", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    fields = verify([i for i in items if isinstance(i, dict)], doc_id, text)
    unverified = [f for f in fields if not f.quote_verified]
    return DocumentExtraction(
        doc_id=doc_id,
        status="degraded" if unverified else "ok",
        fields=fields,
        error=f"{len(unverified)} field(s) with unverifiable quotes" if unverified else None,
        source_chars=len(text),
    )


async def extract_document(doc_id: str, text: str) -> DocumentExtraction:
    """Read one document. Never raises: failure is returned, not thrown."""
    key = _cache_key(doc_id, text)
    if key in _CACHE:
        return _CACHE[key]

    try:
        payload = await gemini.agenerate_json(
            prompt=build_prompt(doc_id, text),
            schema=response_schema(),
        )
        result = _result(doc_id, text, payload)
    except gemini.GeminiUnavailable as exc:
        result = DocumentExtraction(
            doc_id=doc_id, status="failed", error=str(exc), source_chars=len(text)
        )

    _CACHE[key] = result
    return result


async def extract_packet(documents: dict[str, str]) -> list[DocumentExtraction]:
    """Read every document in a packet concurrently, each one blind to the others."""
    results = await asyncio.gather(
        *(extract_document(doc_id, text) for doc_id, text in documents.items())
    )
    return list(results)


def load_packet(case_id: str, overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Read a claim packet from disk. Overrides are applied in memory and never written."""
    case_dir = config.CLAIMS_DIR / case_id
    if not case_dir.is_dir():
        raise FileNotFoundError(f"no claim packet at {case_dir}")

    documents: dict[str, str] = {}
    for doc_id, filename in config.DOCUMENT_FILENAMES.items():
        path = case_dir / filename
        if path.is_file():
            documents[doc_id] = path.read_text(encoding="utf-8")
    for doc_id, text in (overrides or {}).items():
        if doc_id in documents:
            documents[doc_id] = text
    return documents


def cache_stats() -> dict[str, int]:
    return {"entries": len(_CACHE)}
