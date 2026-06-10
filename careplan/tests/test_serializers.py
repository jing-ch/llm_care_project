"""Unit tests for the request serializer (format validation) and output serializers."""
import pytest

from careplan.serializers import (
    GenerateRequestSerializer,
    serialize_careplan,
    serialize_careplan_status,
)
from careplan.models import Provider, Patient, Order, CarePlan

pytestmark = pytest.mark.django_db


def _payload(**overrides):
    p = {
        "referring_provider": "Dr. Smith",
        "referring_provider_npi": "1234567890",
        "patient_mrn": "123456",
        "medication_name": "Lisinopril",
    }
    p.update(overrides)
    return p


def test_valid_payload_passes_and_renames_diagnosis():
    s = GenerateRequestSerializer(data=_payload(patient_primary_diagnosis="HTN"))
    assert s.is_valid(), s.errors
    # frontend's patient_primary_diagnosis -> internal primary_diagnosis (via source)
    assert s.validated_data["primary_diagnosis"] == "HTN"


@pytest.mark.parametrize("npi", ["123", "12345678901", "abcdefghij", ""])
def test_invalid_npi_rejected(npi):
    s = GenerateRequestSerializer(data=_payload(referring_provider_npi=npi))
    assert not s.is_valid()
    assert "referring_provider_npi" in s.errors


@pytest.mark.parametrize("mrn", ["123", "1234567", "abcdef", ""])
def test_invalid_mrn_rejected(mrn):
    s = GenerateRequestSerializer(data=_payload(patient_mrn=mrn))
    assert not s.is_valid()
    assert "patient_mrn" in s.errors


def test_missing_required_fields_reported():
    s = GenerateRequestSerializer(data={"medication_name": "X"})
    assert not s.is_valid()
    assert "referring_provider_npi" in s.errors
    assert "patient_mrn" in s.errors


def test_optional_fields_default():
    s = GenerateRequestSerializer(data=_payload())
    assert s.is_valid(), s.errors
    assert s.validated_data["acknowledge_warnings"] is False
    assert s.validated_data["date_of_birth"] is None


def test_output_serializers():
    provider = Provider.objects.create(npi="1234567890", name="Dr. Smith")
    patient = Patient.objects.create(mrn="123456", first_name="Jane", last_name="Doe")
    order = Order.objects.create(patient=patient, provider=provider, medication_name="Lisinopril")
    cp = CarePlan.objects.create(order=order, content="PLAN", status="completed")

    full = serialize_careplan(cp)
    assert full["id"] == cp.pk
    assert full["care_plan_text"] == "PLAN"
    assert full["patient_first_name"] == "Jane"

    done = serialize_careplan_status(cp)
    assert done["status"] == "completed"
    assert done["content"] == "PLAN"

    cp.status = "pending"
    cp.save(update_fields=["status"])
    pending = serialize_careplan_status(cp)
    assert "content" not in pending  # only completed plans include content
