"""Shared pytest fixtures for the whole project."""
import pytest


@pytest.fixture(autouse=True)
def no_enqueue(mocker):
    """
    Never hit Redis/Celery during tests. submit_careplan_request() ends by calling
    generate_careplan_task.delay(); stub it so the unit/integration tests stay
    in-process. Tests that exercise the task itself call it directly instead.
    """
    from careplan import services
    return mocker.patch.object(services.generate_careplan_task, "delay")


@pytest.fixture
def make_data():
    """
    Factory for a complete `validated_data` dict — the shape services expects
    (i.e. what GenerateRequestSerializer produces). Override any field per test.
    """
    def _make(**overrides):
        data = {
            "referring_provider": "Dr. Smith",
            "referring_provider_npi": "1234567890",
            "patient_first_name": "Jane",
            "patient_last_name": "Doe",
            "patient_mrn": "123456",
            "primary_diagnosis": "Hypertension",
            "medication_name": "Lisinopril",
            "additional_diagnoses": "",
            "medication_history": "",
            "patient_records": "",
            "date_of_birth": None,
            "acknowledge_warnings": False,
        }
        data.update(overrides)
        return data
    return _make
