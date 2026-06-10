"""Unit tests for model __str__ helpers."""
import pytest

from careplan.models import Provider, Patient, Order, CarePlan

pytestmark = pytest.mark.django_db


def test_str_methods():
    provider = Provider.objects.create(npi="1234567890", name="Dr. Smith")
    patient = Patient.objects.create(mrn="123456", first_name="Jane", last_name="Doe")
    order = Order.objects.create(patient=patient, provider=provider, medication_name="Lisinopril")
    cp = CarePlan.objects.create(order=order, content="", status="pending")

    assert "1234567890" in str(provider)
    assert "123456" in str(patient)
    assert "Lisinopril" in str(order)
    assert "pending" in str(cp)
