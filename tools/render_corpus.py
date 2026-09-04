"""Render the claim corpus from the ledger, deterministically, with a manifest.

    python -m tools.render_corpus

Reads eval/cases.json, writes data/claims/<case_id>/*.md and eval/manifests/<case_id>.json.

Two properties this file exists to guarantee:

*Deterministic.* No model call, no randomness. Re-running produces byte-identical output,
so `git diff` after a re-run proves the corpus has not drifted from the ledger.

*Manifested.* Every fact written into a document is recorded as (field, canonical, surface),
where the surface string is verbatim in the document. eval/verify_corpus.py checks the
surfaces are really there, that the canonical values disagree across documents in exactly
the places the ledger plants a contradiction, and that no fact-shaped token appears in a
document without a manifest entry to account for it.

Manifests are written under eval/ rather than beside the documents because CLAUDE.md 2.8
forbids the application from reading eval/ - which makes it structurally impossible for the
app to shortcut extraction by reading pre-extracted values.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tools.corpus_text import FIR_BODIES, NARRATIVES

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases.json"
CLAIMS_DIR = ROOT / "data" / "claims"
MANIFEST_DIR = ROOT / "eval" / "manifests"

FILENAMES = {
    "CLAIM_FORM": "claim_form.md",
    "FIR": "fir.md",
    "REPAIR_ESTIMATE": "repair_estimate.md",
    "CUSTOMER_NARRATIVE": "customer_narrative.md",
}

# Real claim forms are inconsistently labelled between insurers and revisions. Rotating the
# labels is what makes field-label aliasing in phase 4 a real capability rather than a stub.
LABEL_SETS = [
    {"reg": "Registration No.", "date": "Date of Loss", "amount": "Amount Claimed",
     "idv": "Insured Declared Value", "licence": "Driving Licence Valid Upto"},
    {"reg": "Regn No.", "date": "DATE OF INCIDENT", "amount": "Claim Amount (Rs.)",
     "idv": "IDV as per schedule", "licence": "DL Expiry"},
    {"reg": "VEHICLE NO", "date": "Date of accident / loss", "amount": "Estimated Loss",
     "idv": "I.D.V.", "licence": "Licence valid till"},
]

# Damage as the workshop records it on the estimate header. Separate from facts because in
# C06 the estimate deliberately disagrees with the reported point of impact.
ESTIMATE_DAMAGE = {
    "C01": ("front-left", "Front left impact damage"),
    "C03": ("front", "Front end impact damage"),
    "C04": ("rear", "Rear end impact damage"),
    "C06": ("front and rear", "Front and rear impact damage"),
    "C07": ("left side", "Left side impact damage"),
    "C08": ("front-right", "Front right impact damage"),
    "C09": ("rear-left", "Rear left impact damage"),
}

# The workshop writes the customer name as it was given at the counter, not as it appears on
# the policy. C09 declares three spellings of one name as a near miss; this is the third.
ESTIMATE_CUSTOMER_NAME = {"C09": "Rajesh K Singh"}

WORKSHOPS = {
    "C01": ("Sai Motors Authorised Service", "Aundh, Pune"),
    "C03": ("Lanson Toyota Body Shop", "Poonamallee, Chennai"),
    "C04": ("Capital Hyundai Service", "Okhla Phase II, New Delhi"),
    "C06": ("Concorde Motors Body Shop", "Kothrud, Pune"),
    "C07": ("Pink City Auto Works", "Durgapura, Jaipur"),
    "C08": ("Peninsular Honda Service", "Palarivattom, Kochi"),
    "C09": ("Sunrise Automobiles", "Gomti Nagar, Lucknow"),
}


def indian_grouping(amount: int) -> str:
    """1250000 -> '12,50,000'. Lakh-scale grouping, not thousands."""
    digits = str(amount)
    if len(digits) <= 3:
        return digits
    last_three, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return ",".join(groups) + "," + last_three


def fmt_date(iso: str, style: str) -> str:
    value = datetime.strptime(iso, "%Y-%m-%d")
    if style == "dmy_slash":
        return value.strftime("%d/%m/%Y")
    if style == "dmy_dot":
        return value.strftime("%d.%m.%Y")
    if style == "d_mon_y":
        return value.strftime("%d-%b-%Y")
    raise ValueError(f"unknown date style {style!r}")


def fmt_reg(reg: str, style: str) -> str:
    compact = reg.replace("-", "").replace(" ", "").replace(".", "")
    if style == "hyphen":
        return reg
    if style == "compact":
        return compact
    if style == "spaced":
        return " ".join(reg.split("-"))
    raise ValueError(f"unknown registration style {style!r}")


class Document:
    """A rendered document and the manifest entries that account for its content."""

    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        self.lines: list[str] = []
        self.fields: list[dict[str, str]] = []

    def write(self, line: str = "") -> None:
        self.lines.append(line)

    def record(self, field: str, canonical: object, surface: str) -> str:
        self.fields.append({"field": field, "canonical": str(canonical), "surface": surface})
        return surface

    @property
    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def render_claim_form(case: dict, labels: dict[str, str]) -> Document:
    f, doc = case["facts"], Document("CLAIM_FORM")
    theft = case["claim_type"] == "theft"
    date_field = "theft_discovery_date" if theft else "incident_date"

    doc.write("# MOTOR CLAIM FORM")
    doc.write()
    doc.write("Meridian General Insurance Co. Ltd. | Own Damage / Theft")
    doc.write(f"Policy: {f['policy_number']}   |   Claim type: {'Theft' if theft else 'Own Damage'}")
    doc.write()
    doc.write("## 1. Insured and vehicle")
    doc.write()
    doc.write(f"- Name of insured: {doc.record('insured_name', f['insured_name'], f['insured_name'])}")
    doc.write(f"- Make / Model: {doc.record('vehicle_make_model', f['vehicle_make_model'], f['vehicle_make_model'])}")
    doc.write(f"- {labels['reg']}: {doc.record('vehicle_reg', f['vehicle_reg'], fmt_reg(f['vehicle_reg'], 'hyphen'))}")
    doc.write(f"- Cubic capacity: {doc.record('engine_capacity_cc', f['engine_capacity_cc'], str(f['engine_capacity_cc']))} cc")
    doc.write(f"- {labels['idv']}: Rs. {doc.record('insured_declared_value', f['insured_declared_value'], indian_grouping(f['insured_declared_value']))}")
    if not theft:
        doc.write(f"- {labels['licence']}: {doc.record('driving_licence_expiry_date', f['driving_licence_expiry_date'], fmt_date(f['driving_licence_expiry_date'], 'dmy_slash'))}")
        doc.write(f"- Driven by: {doc.record('driver_name', f['driver_name'], f['driver_name'])}")
    doc.write()
    doc.write("## 2. Particulars of loss")
    doc.write()
    doc.write(f"- {labels['date']}: {doc.record(date_field, f[date_field], fmt_date(f[date_field], 'dmy_slash'))}")
    doc.write(f"- Time: {doc.record('incident_time', f['incident_time'], f['incident_time'])} hrs")
    doc.write(f"- Place: {doc.record('incident_location', f['incident_location'], f['incident_location'])}")
    if not theft:
        reported = f["damage_location"]
        doc.write(f"- Part of vehicle damaged: {doc.record('damage_location', reported, reported)}")
    doc.write(f"- Brief description: {f['incident_summary']}")
    doc.write()
    doc.write("## 3. Claim")
    doc.write()
    doc.write(f"- {labels['amount']}: Rs. {doc.record('claim_amount', f['claim_amount'], indian_grouping(f['claim_amount']))}")
    doc.write(f"- Date intimated to insurer: {doc.record('intimation_date', f['intimation_date'], fmt_date(f['intimation_date'], 'dmy_slash'))}")
    doc.write(f"- Date documents submitted: {doc.record('document_submission_date', f['document_submission_date'], fmt_date(f['document_submission_date'], 'dmy_slash'))}")
    if theft:
        doc.write(f"- FIR lodged: {'Yes' if 'FIR' in case['documents'] else 'Not yet - to follow'}")
    doc.write()
    doc.write("I declare that the particulars given above are true to the best of my knowledge.")
    doc.write()
    doc.write(f"Signature: {f['insured_name']}")
    return doc


def render_fir(case: dict) -> Document:
    f, doc = case["facts"], Document("FIR")
    body = FIR_BODIES[case["case_id"]]

    doc.write("FIRST INFORMATION REPORT")
    doc.write("(Under Section 173 of the Bharatiya Nagarik Suraksha Sanhita, 2023)")
    doc.write()
    doc.write(f"Police Station: {doc.record('police_station', f['police_station'], f['police_station'])}")
    doc.write(f"FIR No.: {doc.record('fir_number', f['fir_number'], f['fir_number'])}")
    doc.write(f"Date of report: {doc.record('fir_date', f['fir_date'], fmt_date(f['fir_date'], 'dmy_dot'))}")
    doc.write()
    doc.write("BRIEF FACTS OF THE CASE")
    doc.write()
    doc.write(str(body["text"]).rstrip())
    doc.write()
    doc.write("Recorded and forwarded to the Court concerned.")
    doc.write()
    doc.write("Station House Officer")

    for field, canonical, surface in body["fields"]:  # type: ignore[misc]
        doc.record(field, canonical, surface)
    return doc


def render_repair_estimate(case: dict) -> Document:
    f, doc = case["facts"], Document("REPAIR_ESTIMATE")
    cid = case["case_id"]
    workshop, place = WORKSHOPS[cid]
    damage_canonical, damage_surface = ESTIMATE_DAMAGE[cid]

    doc.write(f"{workshop.upper()}")
    doc.write(f"{place}   |   GSTIN 27AAECS1234F1ZV")
    doc.write()
    doc.write("REPAIR ESTIMATE")
    doc.write()
    doc.write(f"Vehicle      : {f['vehicle_make_model']}")
    doc.write(f"Regn         : {doc.record('vehicle_reg', f['vehicle_reg'], fmt_reg(f['vehicle_reg'], 'compact'))}")
    counter_name = ESTIMATE_CUSTOMER_NAME.get(cid, f["insured_name"])
    doc.write(f"Customer     : {doc.record('insured_name', f['insured_name'], counter_name)}")
    doc.write(f"Date in      : {doc.record('estimate_date', f['document_submission_date'], fmt_date(f['document_submission_date'], 'd_mon_y'))}")
    doc.write(f"Damage seen  : {doc.record('damage_location', damage_canonical, damage_surface)}")
    doc.write()
    doc.write("| Part code | Description | Amount |")
    doc.write("|---|---|---|")
    for line in f["estimate_lines"]:
        amount = doc.record("estimate_line_amount", line["amount"], f"{line['amount']}.00")
        doc.write(f"| {line['part_code']} | {line['description']} | {amount} |")
    doc.write()

    total = f["claim_amount"]
    subtotal = f.get("estimate_subtotal")
    if subtotal is not None:
        gst_percent = f["estimate_gst_percent"]
        gst_amount = total - subtotal
        sub_surface = doc.record("estimate_subtotal", subtotal, "{}.00".format(subtotal))
        gst_surface = doc.record("estimate_gst_amount", gst_amount, "{}.00".format(gst_amount))
        doc.write("Sub-total                        {}".format(sub_surface))
        doc.write("GST @ {}%                       {}".format(gst_percent, gst_surface))
    total_surface = doc.record("claim_amount", total, "{}.00".format(total))
    doc.write("TOTAL ESTIMATE                   {}".format(total_surface))
    doc.write()
    doc.write("Estimate only. Subject to inspection on dismantling. Parts subject to availability.")
    return doc


def render_narrative(case: dict) -> Document:
    doc = Document("CUSTOMER_NARRATIVE")
    entry = NARRATIVES[case["case_id"]]

    doc.write(f"## {entry['title']}")
    doc.write()
    doc.write(str(entry["text"]).rstrip())

    for field, canonical, surface in entry["fields"]:  # type: ignore[misc]
        doc.record(field, canonical, surface)
    return doc


def render_case(case: dict, label_index: int) -> dict:
    cid = case["case_id"]
    out_dir = CLAIMS_DIR / cid
    out_dir.mkdir(parents=True, exist_ok=True)

    renderers = {
        "CLAIM_FORM": lambda: render_claim_form(case, LABEL_SETS[label_index]),
        "FIR": lambda: render_fir(case),
        "REPAIR_ESTIMATE": lambda: render_repair_estimate(case),
        "CUSTOMER_NARRATIVE": lambda: render_narrative(case),
    }

    manifest: dict[str, object] = {"case_id": cid, "claim_type": case["claim_type"], "documents": {}}
    for doc_id in case["documents"]:
        doc = renderers[doc_id]()
        path = out_dir / FILENAMES[doc_id]
        path.write_text(doc.text, encoding="utf-8", newline="\n")
        manifest["documents"][doc_id] = {  # type: ignore[index]
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "fields": doc.fields,
        }
    return manifest


def main() -> int:
    ledger = json.loads(CASES.read_text(encoding="utf-8"))
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for index, case in enumerate(ledger["cases"]):
        if case.get("status") == "placeholder":
            continue
        manifest = render_case(case, index % len(LABEL_SETS))
        (MANIFEST_DIR / f"{case['case_id']}.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        count = len(manifest["documents"])  # type: ignore[arg-type]
        written += count
        print(f"  {case['case_id']}  {count} documents  "
              f"{sum(len(d['fields']) for d in manifest['documents'].values())} manifested fields")

    print(f"rendered {written} documents into data/claims/, manifests into eval/manifests/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
