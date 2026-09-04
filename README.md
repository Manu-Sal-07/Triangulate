TRACK_ID=PS02

# Claims Evidence Review Assistant

A motor-insurance claims investigator uploads or selects a claim packet — claim form,
FIR or repair estimate, and the customer's incident description — and this system reviews
it against a motor policy, producing a **claim review**: what was submitted, what is
missing, where the documents contradict each other, which policy clauses apply, and a
recommendation for the investigator. Every finding cites the document or clause it came
from.

The system flags and explains. It does not approve claims — a human does.

## Run it

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your-key-here     # Windows: set GEMINI_API_KEY=your-key-here
python app.py
```

Then open <http://localhost:8000>.

`GEMINI_API_KEY` is the only environment variable required. The Gemini API is the only
external service this project calls.

## Status

Phase 0 — skeleton. The review pipeline, evaluation numbers and demo video link follow.
