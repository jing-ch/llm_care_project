"""Unit tests for Provider and Order rules in services.submit_careplan_request."""
import datetime

import pytest
from django.utils import timezone

from careplan import errors, services
from careplan.models import Provider, Order, CarePlan

pytestmark = pytest.mark.django_db


# ── Provider ────────────────────────────────────────────────────────────────

def test_new_provider_is_created(make_data):
    services.submit_careplan_request(make_data())
    assert Provider.objects.filter(npi="1234567890").count() == 1


def test_same_npi_same_name_is_reused(make_data):
    Provider.objects.create(npi="1234567890", name="Dr. Smith")
    services.submit_careplan_request(make_data(referring_provider="Dr. Smith"))
    assert Provider.objects.filter(npi="1234567890").count() == 1


def test_same_npi_different_name_blocks(make_data):
    Provider.objects.create(npi="1234567890", name="Dr. Smith")
    with pytest.raises(errors.BlockError) as exc:
        services.submit_careplan_request(make_data(referring_provider="Dr. Jones"))
    assert exc.value.code == "PROVIDER_NAME_CONFLICT"
    assert exc.value.http_status == 409
    assert CarePlan.objects.count() == 0  # blocked before any write


def test_blank_submitted_name_does_not_conflict(make_data):
    Provider.objects.create(npi="1234567890", name="Dr. Smith")
    result = services.submit_careplan_request(make_data(referring_provider=""))
    assert result["status"] == "pending"  # reused, no conflict


# ── Order ───────────────────────────────────────────────────────────────────

def test_same_patient_med_same_day_blocks(make_data):
    services.submit_careplan_request(make_data())          # first order today
    with pytest.raises(errors.BlockError) as exc:
        services.submit_careplan_request(make_data())      # same patient + med + day
    assert exc.value.code == "DUPLICATE_ORDER_TODAY"
    assert exc.value.http_status == 409


def test_same_patient_med_other_day_warns(make_data):
    services.submit_careplan_request(make_data())          # order "today"
    # Backdate it (update() skips auto_now_add) so it looks like another day.
    Order.objects.update(created_at=timezone.now() - datetime.timedelta(days=1))
    with pytest.raises(errors.WarningException) as exc:
        services.submit_careplan_request(make_data())
    codes = {w["code"] for w in exc.value.detail["warnings"]}
    assert "DUPLICATE_ORDER_OTHER_DAY" in codes


# ── _to_list helper ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (None, []),
    ("", []),
    ("aspirin", ["aspirin"]),
    (["a", "b"], ["a", "b"]),
    (123, ["123"]),
])
def test_to_list(value, expected):
    assert services._to_list(value) == expected
