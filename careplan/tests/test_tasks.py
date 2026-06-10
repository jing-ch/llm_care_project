"""Unit tests for the Celery task — called directly (no worker/broker)."""
import pytest

from careplan import tasks
from careplan.models import Provider, Patient, Order, CarePlan

pytestmark = pytest.mark.django_db


def _make_careplan():
    provider = Provider.objects.create(npi="1234567890", name="Dr. Smith")
    patient = Patient.objects.create(mrn="123456", first_name="Jane", last_name="Doe")
    order = Order.objects.create(patient=patient, provider=provider, medication_name="Lisinopril")
    return CarePlan.objects.create(order=order, content="", status="pending")


def test_mock_llm_path_completes(monkeypatch, mocker):
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    mocker.patch("careplan.tasks.time.sleep")  # skip the simulated latency
    cp = _make_careplan()

    tasks.generate_careplan_task(cp.pk)

    cp.refresh_from_db()
    assert cp.status == "completed"
    assert "MOCK" in cp.content


def test_missing_careplan_returns_none():
    assert tasks.generate_careplan_task(999999) is None


def test_retries_on_llm_error(mocker):
    cp = _make_careplan()
    mocker.patch("careplan.tasks._call_llm", side_effect=RuntimeError("boom"))
    # Called directly (not via a worker), self.retry() re-raises the original
    # exception rather than the Retry signal — but it first resets status to
    # 'pending', which is what distinguishes the retry branch from the fail branch.
    with pytest.raises(RuntimeError):
        tasks.generate_careplan_task(cp.pk)
    cp.refresh_from_db()
    assert cp.status == "pending"


def test_fails_after_retries_exhausted(mocker):
    cp = _make_careplan()
    mocker.patch("careplan.tasks._call_llm", side_effect=RuntimeError("boom"))
    mocker.patch.object(tasks.generate_careplan_task, "max_retries", 0)
    with pytest.raises(RuntimeError):
        tasks.generate_careplan_task(cp.pk)
    cp.refresh_from_db()
    assert cp.status == "failed"
