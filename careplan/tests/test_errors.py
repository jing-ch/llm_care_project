"""Unit tests for the exception hierarchy and the single exception handler."""
from rest_framework import exceptions as drf_exceptions

from careplan import errors


# ── Exception classes ──────────────────────────────────────────────────────

def test_base_exception_defaults():
    e = errors.BaseAppException()
    assert e.to_dict() == {
        "type": "error",
        "code": "error",
        "message": "Something went wrong.",
        "detail": {},
    }


def test_subclass_status_codes():
    assert errors.ValidationError().http_status == 400
    assert errors.BlockError().http_status == 409
    assert errors.WarningException().http_status == 200


def test_instance_overrides_message_code_detail():
    e = errors.BlockError("nope", code="X_CONFLICT", detail={"a": 1})
    assert e.to_dict() == {
        "type": "block",
        "code": "X_CONFLICT",
        "message": "nope",
        "detail": {"a": 1},
    }


# ── Handler — one branch per kind of exception ──────────────────────────────

def test_handler_handles_app_exception():
    resp = errors.app_exception_handler(errors.BlockError("no"), {})
    assert resp.status_code == 409
    assert resp.data["type"] == "block"


def test_handler_wraps_drf_validation_error():
    exc = drf_exceptions.ValidationError({"field": ["bad"]})
    resp = errors.app_exception_handler(exc, {})
    assert resp.status_code == 400
    assert resp.data["type"] == "validation_error"
    assert resp.data["detail"] == {"field": ["bad"]}


def test_handler_normalizes_other_drf_exception():
    resp = errors.app_exception_handler(
        drf_exceptions.NotFound(), {"request": None, "view": None}
    )
    assert resp.status_code == 404
    assert resp.data["type"] == "not_found"
    assert resp.data["message"]


def test_handler_sanitizes_unexpected_exception():
    resp = errors.app_exception_handler(
        RuntimeError("secret stack trace"), {"request": None, "view": None}
    )
    assert resp.status_code == 500
    assert resp.data["type"] == "server_error"
    assert "secret" not in str(resp.data)  # never leak internals
