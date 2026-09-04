"""Domain objects shared across module boundaries.

No free-floating dicts between modules (CLAUDE.md section 4). Every extracted value carries
its provenance - the document it came from and a quote that is verbatim in that document -
because a value without provenance cannot be cited, and a finding without a citation is a
bug (CLAUDE.md section 3.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DocId = Literal["CLAIM_FORM", "FIR", "REPAIR_ESTIMATE", "CUSTOMER_NARRATIVE"]
Confidence = Literal["high", "low"]


@dataclass
class ExtractedField:
    """One fact read out of one document.

    `raw` is the value as it appeared; `value` is filled in by normalisation in phase 4 and
    is what reconciliation compares. Keeping both is what lets the report say "MH-12-AB-1234
    and MH12AB1234 are the same registration" instead of silently discarding the difference.
    """

    name: str
    raw: str
    doc_id: str
    exact_quote: str
    confidence: Confidence = "high"
    value: Any = None
    quote_verified: bool = False
    quote_problem: str | None = None

    @property
    def cited(self) -> str:
        return f"{self.doc_id}: {self.exact_quote!r}"


@dataclass
class DocumentExtraction:
    """The outcome of reading one document, successful or not.

    A failed extraction is a first-class result rather than an exception, so that one
    unreadable document degrades to "could not extract - escalated" while the rest of the
    packet proceeds (CLAUDE.md section 3.7).
    """

    doc_id: str
    status: Literal["ok", "degraded", "failed"]
    fields: list[ExtractedField] = field(default_factory=list)
    error: str | None = None
    source_chars: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def by_name(self, name: str) -> ExtractedField | None:
        for item in self.fields:
            if item.name == name:
                return item
        return None
