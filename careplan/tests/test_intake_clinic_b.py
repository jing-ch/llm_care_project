"""
Unit tests for the Clinic B intake adapter (and, through it, the BaseIntakeAdapter
pipeline and InternalOrder canonical format). Pure logic — no DB.
"""
import json
from datetime import date

import pytest

from careplan.errors import ValidationError
from careplan.intake import BaseIntakeAdapter, ClinicBAdapter
from careplan.internal_order import InternalOrder


def _payload(**overrides):
    p = {
        "clinic": "Westside Family Clinic",
        "order_ref": "WFC-2024-00871",
        "patient": {
            "given": "Maria",
            "family": "Gonzalez",
            "record_number": "002145",
            "birthdate": "1980-07-22",
        },
        "ordering_md": {"full_name": "Dr. Alan Pierce", "npi_number": "1932087654"},
        "rx": {
            "drug_name": "Metformin 500mg",
            "diagnosis": "Type 2 Diabetes Mellitus",
            "other_dx": ["Hypertension", "Hyperlipidemia"],
            "prior_meds": ["Glipizide 5mg"],
        },
        "notes": "Occasional GI upset.",
    }
    p.update(overrides)
    return p


# ── happy path: full mapping ────────────────────────────────────────────────

def test_process_maps_every_field():
    order = ClinicBAdapter().process(_payload())

    assert isinstance(order, InternalOrder)
    assert order.patient.first_name == "Maria"
    assert order.patient.last_name == "Gonzalez"
    assert order.patient.mrn == "002145"
    assert order.patient.date_of_birth == date(1980, 7, 22)
    assert order.provider.name == "Dr. Alan Pierce"
    assert order.provider.npi == "1932087654"
    assert order.medication.name == "Metformin 500mg"
    assert order.medication.primary_diagnosis == "Type 2 Diabetes Mellitus"
    assert order.medication.additional_diagnoses == ["Hypertension", "Hyperlipidemia"]
    assert order.medication.medication_history == ["Glipizide 5mg"]
    assert order.patient_records == "Occasional GI upset."
    assert order.source == "clinic_b"
    assert order.source_order_id == "WFC-2024-00871"


def test_accepts_json_string_and_dict_equivalently():
    payload = _payload()
    from_dict = ClinicBAdapter().process(payload)
    from_str = ClinicBAdapter().process(json.dumps(payload))
    assert from_dict == from_str


# ── raw payload preserved for troubleshooting ───────────────────────────────

def test_raw_payload_is_preserved():
    payload = _payload()
    order = ClinicBAdapter().process(payload)
    assert order.raw == payload
    assert order.raw["order_ref"] == "WFC-2024-00871"


def test_raw_excluded_from_repr_so_phi_does_not_leak():
    order = ClinicBAdapter().process(_payload())
    assert "raw=" not in repr(order)
    assert "Gonzalez" not in repr(order.raw.__class__.__name__)  # sanity, no crash


# ── parse() error handling ──────────────────────────────────────────────────

def test_malformed_json_raises_validation_error():
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process("{not valid json")
    assert exc.value.type == "validation_error"


def test_non_object_json_raises_validation_error():
    with pytest.raises(ValidationError):
        ClinicBAdapter().process("[1, 2, 3]")


# ── date_of_birth parsing ───────────────────────────────────────────────────

def test_missing_dob_becomes_none():
    payload = _payload()
    payload["patient"].pop("birthdate")
    order = ClinicBAdapter().process(payload)
    assert order.patient.date_of_birth is None


def test_bad_dob_format_raises_validation_error():
    payload = _payload()
    payload["patient"]["birthdate"] = "22/07/1980"  # not ISO
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process(payload)
    assert exc.value.detail["field"] == "patient.birthdate"


# ── validate(): canonical format rules ──────────────────────────────────────

def test_bad_npi_and_mrn_reported_together_without_phi():
    payload = _payload()
    payload["patient"]["record_number"] = "12"      # too short
    payload["ordering_md"]["npi_number"] = "abc"    # not 10 digits
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process(payload)
    fields = exc.value.detail["fields"]
    assert "mrn" in fields and "npi" in fields
    # traceability without leaking PHI values
    assert exc.value.detail["source"] == "clinic_b"
    assert exc.value.detail["source_order_id"] == "WFC-2024-00871"
    assert "Gonzalez" not in json.dumps(exc.value.detail)


def test_missing_patient_name_rejected():
    payload = _payload()
    payload["patient"]["given"] = ""
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process(payload)
    assert "patient_name" in exc.value.detail["fields"]


def test_missing_provider_name_rejected():
    payload = _payload()
    payload["ordering_md"]["full_name"] = ""
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process(payload)
    assert "provider_name" in exc.value.detail["fields"]


def test_missing_medication_rejected():
    payload = _payload()
    payload["rx"]["drug_name"] = ""
    with pytest.raises(ValidationError) as exc:
        ClinicBAdapter().process(payload)
    assert "medication_name" in exc.value.detail["fields"]


def test_missing_sections_do_not_crash_transform():
    # A nearly empty payload should fail validation cleanly, not raise KeyError.
    with pytest.raises(ValidationError):
        ClinicBAdapter().process({"order_ref": "X"})


# ── BaseIntakeAdapter contract ──────────────────────────────────────────────

def test_base_adapter_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseIntakeAdapter()


def test_base_abstract_methods_raise_when_called_via_super():
    # A subclass that defers to the base implementations documents the contract:
    # the three steps must be overridden.
    class Incomplete(BaseIntakeAdapter):
        def parse(self, raw):
            return super().parse(raw)

        def transform(self, parsed):
            return super().transform(parsed)

        def validate(self, order):
            return super().validate(order)

    adapter = Incomplete()
    with pytest.raises(NotImplementedError):
        adapter.parse({})
    with pytest.raises(NotImplementedError):
        adapter.transform({})
    with pytest.raises(NotImplementedError):
        adapter.validate(None)
