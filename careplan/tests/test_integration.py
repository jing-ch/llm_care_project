"""
Integration tests: real HTTP requests through the DRF stack (urls -> views ->
serializer -> services -> exception handler). These assert the unified envelope
the frontend relies on: a body with no `type` is success; otherwise `type` says
what happened.
"""
import pytest
from rest_framework.test import APIClient

from careplan.models import Provider, Patient, CarePlan

pytestmark = pytest.mark.django_db

GENERATE = "/api/generate-careplan/"


@pytest.fixture
def client():
    return APIClient()


def _payload(**overrides):
    p = {
        "referring_provider": "Dr. Smith",
        "referring_provider_npi": "1234567890",
        "patient_first_name": "Jane",
        "patient_last_name": "Doe",
        "patient_mrn": "123456",
        "medication_name": "Lisinopril",
    }
    p.update(overrides)
    return p


def test_home_page_serves(client):
    assert client.get("/").status_code == 200


def test_success_has_no_envelope_type(client):
    res = client.post(GENERATE, _payload(), format="json")
    assert res.status_code == 202
    assert "care_plan_id" in res.data
    assert "type" not in res.data


def test_invalid_input_returns_validation_error(client):
    res = client.post(GENERATE, _payload(referring_provider_npi="123", patient_mrn="1"), format="json")
    assert res.status_code == 400
    assert res.data["type"] == "validation_error"
    assert "referring_provider_npi" in res.data["detail"]
    assert "patient_mrn" in res.data["detail"]


def test_provider_conflict_blocks(client):
    Provider.objects.create(npi="1234567890", name="Dr. Smith")
    res = client.post(GENERATE, _payload(referring_provider="Dr. Jones"), format="json")
    assert res.status_code == 409
    assert res.data["type"] == "block"
    assert res.data["code"] == "PROVIDER_NAME_CONFLICT"


def test_warning_then_acknowledge_flow(client):
    Patient.objects.create(mrn="123456", first_name="John", last_name="Smith")

    warn = client.post(GENERATE, _payload(), format="json")
    assert warn.status_code == 200
    assert warn.data["type"] == "warning"
    assert warn.data["detail"]["warnings"]

    ok = client.post(GENERATE, _payload(acknowledge_warnings=True), format="json")
    assert ok.status_code == 202
    assert "care_plan_id" in ok.data


def test_duplicate_order_same_day_blocks(client):
    client.post(GENERATE, _payload(), format="json")
    res = client.post(GENERATE, _payload(), format="json")
    assert res.status_code == 409
    assert res.data["code"] == "DUPLICATE_ORDER_TODAY"


def test_wrong_method_is_405_envelope(client):
    res = client.get(GENERATE)
    assert res.status_code == 405
    assert res.data["type"] == "method_not_allowed"


def test_status_not_found(client):
    assert client.get("/api/careplan/99999/status/").status_code == 404


def test_status_get_download_search(client):
    created = client.post(GENERATE, _payload(), format="json")
    cp_id = created.data["care_plan_id"]

    cp = CarePlan.objects.get(pk=cp_id)
    cp.content = "FULL PLAN"
    cp.status = "completed"
    cp.save(update_fields=["content", "status"])

    assert client.get(f"/api/careplan/{cp_id}/status/").data["status"] == "completed"
    assert client.get(f"/api/careplan/{cp_id}/").data["care_plan_text"] == "FULL PLAN"

    dl = client.get(f"/api/careplan/{cp_id}/download/")
    assert dl.status_code == 200
    assert b"FULL PLAN" in dl.content

    search = client.get("/api/careplan/search/?q=Jane")
    assert search.status_code == 200
    assert len(search.data["results"]) >= 1

    # not-found branches of the GET/download views
    assert client.get("/api/careplan/99999/").status_code == 404
    assert client.get("/api/careplan/99999/download/").status_code == 404
