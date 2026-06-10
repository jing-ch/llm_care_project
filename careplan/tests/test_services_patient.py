"""
Unit tests for Patient duplicate-detection rules in services.submit_careplan_request.

Business rules under test (CLAUDE.md):
  - same MRN + different name or DOB  -> WARNING
  - same name + DOB + different MRN    -> WARNING
  - same MRN + same name (+ DOB)       -> reuse, no warning
A warning halts the flow (nothing is written) until the user acknowledges it.
"""
import datetime

import pytest

from careplan import errors, services
from careplan.models import Patient, CarePlan

pytestmark = pytest.mark.django_db

DOB = datetime.date(1990, 5, 17)


def _seed_patient(mrn="123456", first="Jane", last="Doe", dob=None):
    return Patient.objects.create(mrn=mrn, first_name=first, last_name=last, date_of_birth=dob)


def _warning_codes(exc_info):
    return {w["code"] for w in exc_info.value.detail["warnings"]}


def test_new_patient_is_created_and_succeeds(make_data):
    result = services.submit_careplan_request(make_data())
    assert result["status"] == "pending"
    assert "care_plan_id" in result
    assert Patient.objects.filter(mrn="123456").count() == 1


def test_same_mrn_same_name_reuses_without_warning(make_data):
    _seed_patient(first="Jane", last="Doe")
    result = services.submit_careplan_request(make_data())  # identical name
    assert result["status"] == "pending"
    assert Patient.objects.filter(mrn="123456").count() == 1  # reused, not duplicated


def test_same_mrn_different_name_warns(make_data):
    _seed_patient(first="John", last="Smith")
    with pytest.raises(errors.WarningException) as exc:
        services.submit_careplan_request(make_data(patient_first_name="Jane", patient_last_name="Doe"))
    assert "PATIENT_NAME_MISMATCH" in _warning_codes(exc)
    assert exc.value.http_status == 200


def test_same_mrn_different_dob_warns(make_data):
    _seed_patient(dob=datetime.date(1980, 1, 1))  # same name, different DOB on file
    with pytest.raises(errors.WarningException) as exc:
        services.submit_careplan_request(make_data(date_of_birth=DOB))
    assert "PATIENT_DOB_MISMATCH" in _warning_codes(exc)


def test_same_name_and_dob_under_different_mrn_warns(make_data):
    _seed_patient(mrn="999999", first="Jane", last="Doe", dob=DOB)
    with pytest.raises(errors.WarningException) as exc:
        services.submit_careplan_request(make_data(patient_mrn="123456", date_of_birth=DOB))
    assert "PATIENT_MRN_MISMATCH" in _warning_codes(exc)


def test_multiple_patient_warnings_combine(make_data):
    _seed_patient(first="John", last="Smith", dob=datetime.date(1970, 2, 2))
    with pytest.raises(errors.WarningException) as exc:
        services.submit_careplan_request(make_data(date_of_birth=DOB))
    assert {"PATIENT_NAME_MISMATCH", "PATIENT_DOB_MISMATCH"} <= _warning_codes(exc)


def test_dob_rules_dormant_when_dob_not_supplied(make_data):
    # On-file DOB present, but request omits DOB -> no DOB-based warning fires.
    _seed_patient(first="Jane", last="Doe", dob=DOB)
    result = services.submit_careplan_request(make_data(date_of_birth=None))
    assert result["status"] == "pending"  # name matches, no warning


def test_acknowledge_bypasses_warning_and_creates(make_data):
    _seed_patient(first="John", last="Smith")
    result = services.submit_careplan_request(make_data(acknowledge_warnings=True))
    assert result["status"] == "pending"
    assert CarePlan.objects.count() == 1


def test_warning_commits_nothing(make_data):
    _seed_patient(first="John", last="Smith")
    with pytest.raises(errors.WarningException):
        services.submit_careplan_request(make_data())
    # nothing was written: no new patient, no order, no care plan
    assert CarePlan.objects.count() == 0
    assert Patient.objects.count() == 1  # only the seeded one
