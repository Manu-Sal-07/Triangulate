"""Every tunable constant in one place, overridable by environment variable.

Model ids live here and nowhere else (CLAUDE.md section 4). The API key is read from the
environment only - never from a file, never hardcoded (CLAUDE.md section 2.5). A judge sets
GEMINI_API_KEY in their shell and runs the app; that is the only supported path, so it is
also the path we develop against.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Gemini ------------------------------------------------------------------------------
API_KEY_ENV = "GEMINI_API_KEY"
LLM_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

REQUEST_TIMEOUT_SECONDS = float(os.environ.get("GEMINI_TIMEOUT", "20"))
MAX_ATTEMPTS = int(os.environ.get("GEMINI_MAX_ATTEMPTS", "2"))
BACKOFF_SECONDS = float(os.environ.get("GEMINI_BACKOFF", "1.5"))

# An internal budget below the 60s the brief allows, so that we decide what a slow request
# returns instead of the transport deciding for us.
REVIEW_BUDGET_SECONDS = float(os.environ.get("REVIEW_BUDGET", "45"))

# --- Data --------------------------------------------------------------------------------
CLAIMS_DIR = ROOT / "data" / "claims"
POLICY_DIR = ROOT / "data" / "policy"
CLAUSES_PATH = POLICY_DIR / "clauses.json"

DOCUMENT_FILENAMES = {
    "CLAIM_FORM": "claim_form.md",
    "FIR": "fir.md",
    "REPAIR_ESTIMATE": "repair_estimate.md",
    "CUSTOMER_NARRATIVE": "customer_narrative.md",
}


def api_key() -> str | None:
    """The key, or None. Absence is a degraded mode, not a crash (CLAUDE.md section 3.7)."""
    value = os.environ.get(API_KEY_ENV, "").strip()
    return value or None
