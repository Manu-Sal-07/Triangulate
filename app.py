"""NexusTiq24 PS02 - Insurance Claims Evidence Review Assistant.

Single entry point. `python app.py` starts the API and serves the frontend
together on http://localhost:8000 - no second terminal, no build step.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

TRACK_ID = "PS02"
ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

app = FastAPI(
    title="Claims Evidence Review Assistant",
    description="Reviews a motor insurance claim packet against a motor policy.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> JSONResponse:
    """Liveness probe. Answering here is the contract judges check first."""
    return JSONResponse(
        {
            "status": "ok",
            "track_id": TRACK_ID,
            "version": app.version,
        }
    )


# Mounted last so /api/* routes win. html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
