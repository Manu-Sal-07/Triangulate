"""The closed field vocabulary that extraction and reconciliation both speak.

Reconciliation compares fields *by name*. If the claim form yielded `date_of_loss` and the
FIR yielded `incident_date`, the matrix would never put them side by side and the
contradiction would silently vanish - so the vocabulary is fixed here, in one place, and the
prompt is generated from it rather than written by hand and drifting.

Closed rather than open on purpose. An open vocabulary reads whatever a document happens to
mention, which sounds better and is worse: two documents describing the same fact under two
spontaneous names are not comparable, and the failure is invisible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str          # date | time | money | integer | text | enum
    description: str
    documents: tuple[str, ...] = ()   # empty means: look for it in any document


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("insured_name", "text", "Full name of the insured person as written here."),
    FieldSpec("driver_name", "text", "Name of the person driving at the time of the incident."),
    FieldSpec("policy_number", "text", "The insurance policy number."),
    FieldSpec("vehicle_make_model", "text", "Make and model of the insured vehicle."),
    FieldSpec("vehicle_reg", "text", "Vehicle registration number, exactly as written."),
    FieldSpec("engine_capacity_cc", "integer", "Engine capacity or cubic capacity in cc."),
    FieldSpec("insured_declared_value", "money", "The Insured Declared Value (IDV) from the policy schedule."),
    FieldSpec("claim_amount", "money", "The amount being claimed, or the total of a repair estimate."),
    FieldSpec("estimate_subtotal", "money", "A repair estimate sub-total before tax, if one is shown separately."),
    FieldSpec("incident_date", "date", "Date the accident or incident occurred."),
    FieldSpec("incident_time", "time", "Time of day the incident occurred, however it is expressed."),
    FieldSpec("incident_location", "text", "Where the incident occurred."),
    FieldSpec("damage_location", "text", "Which part of the vehicle was damaged, or where the impact was."),
    FieldSpec("theft_discovery_date", "date", "Date the theft was discovered, for a theft claim."),
    FieldSpec("intimation_date", "date", "Date the claim was reported or intimated to the insurer."),
    FieldSpec("intimation_time", "time", "Time the claim was reported to the insurer, if stated."),
    FieldSpec("document_submission_date", "date", "Date the claim documents were submitted."),
    FieldSpec("fir_date", "date", "Date the First Information Report was lodged with the police."),
    FieldSpec("fir_number", "text", "The FIR number."),
    FieldSpec("police_station", "text", "Name of the police station where the FIR was lodged."),
    FieldSpec("driving_licence_expiry_date", "date", "Date the driving licence expires or is valid until."),
    FieldSpec("vehicle_use", "enum", "How the vehicle was being used: private, or commercial / for hire or reward / carrying goods for payment."),
)

FIELD_NAMES = tuple(spec.name for spec in FIELD_SPECS)
BY_NAME = {spec.name: spec for spec in FIELD_SPECS}


def prompt_field_list() -> str:
    """The vocabulary rendered for the prompt, so the two can never disagree."""
    return "\n".join(f"- `{spec.name}` ({spec.kind}) - {spec.description}" for spec in FIELD_SPECS)


def response_schema() -> dict:
    """JSON Schema for the structured-output response."""
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": list(FIELD_NAMES)},
                        "raw": {"type": "string"},
                        "exact_quote": {"type": "string"},
                    },
                    "required": ["name", "raw", "exact_quote"],
                },
            }
        },
        "required": ["fields"],
    }
