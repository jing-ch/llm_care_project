"""
errors.py — unified error handling.

Every abnormal response shares one envelope: {type, code, message, detail}.
Views and services just `raise`; this module owns the JSON shape and the HTTP
status code, so if you ever need to change the format you change it in exactly
one place (the handler below).

Frontend contract
-----------------
A response is "abnormal" iff its body has a `type` key. One branch handles all:

    const data = await res.json();
    switch (data.type) {
      case undefined:           // success — use the normal payload
      case 'warning':           // 200 — show data.detail.warnings, let user confirm
      case 'validation_error':  // 400 — bad input, show data.detail (per field)
      case 'block':             // 409 — business rule forbids it, show data.message
      default:                  // server_error / anything else
    }
"""
import logging

from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


# ── Exception hierarchy ──────────────────────────────────────────────────────

class BaseAppException(Exception):
    """
    Base for all app-level errors. Subclasses declare `type` / `code` /
    `http_status`; instances may override `message`, `code`, and `detail`.
    """
    type = 'error'
    code = 'error'
    http_status = 400
    default_message = 'Something went wrong.'

    def __init__(self, message=None, *, code=None, detail=None):
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        self.detail = detail if detail is not None else {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            'type': self.type,
            'code': self.code,
            'message': self.message,
            'detail': self.detail,
        }


class ValidationError(BaseAppException):
    """Input is malformed (e.g. NPI not 10 digits). -> 400"""
    type = 'validation_error'
    code = 'validation_error'
    http_status = 400
    default_message = 'Validation failed.'


class BlockError(BaseAppException):
    """A business rule forbids this action outright. -> 409"""
    type = 'block'
    code = 'block'
    http_status = 409
    default_message = 'This action is not allowed.'


class WarningException(BaseAppException):
    """Allowed, but the user must confirm before continuing. -> 200 + warnings"""
    type = 'warning'
    code = 'warning'
    http_status = 200
    default_message = 'Please review before continuing.'


# ── The single exception handler ─────────────────────────────────────────────

def _envelope(type_, code, message, detail):
    return {'type': type_, 'code': code, 'message': message, 'detail': detail}


def app_exception_handler(exc, context):
    """
    Turn any exception raised inside a DRF view into the unified envelope.
    Wired via settings.REST_FRAMEWORK['EXCEPTION_HANDLER'].
    """
    # 1. Our own exceptions — already the right shape and status.
    if isinstance(exc, BaseAppException):
        return Response(exc.to_dict(), status=exc.http_status)

    # 2. DRF serializer validation, i.e. serializer.is_valid(raise_exception=True).
    #    Reuse its per-field detail, but wrap it in our envelope so the frontend
    #    sees the same shape as everything else.
    if isinstance(exc, drf_exceptions.ValidationError):
        return Response(
            _envelope('validation_error', 'validation_error',
                      'Validation failed.', exc.detail),
            status=exc.status_code,
        )

    # 3. Any other DRF exception (404, 405, throttling, ...). Normalize too.
    response = drf_exception_handler(exc, context)
    if response is not None:
        data = response.data
        message = str(data['detail']) if isinstance(data, dict) and 'detail' in data else 'Request failed.'
        detail = data if isinstance(data, dict) else {'detail': data}
        code = getattr(exc, 'default_code', 'error')
        response.data = _envelope(code, code, message, detail)
        return response

    # 4. Unexpected crash. Log the traceback server-side and return a generic
    #    message — never leak stack traces or PHI in the response (project rule).
    logger.exception('Unhandled exception in API request')
    return Response(
        _envelope('server_error', 'server_error', 'An internal error occurred.', {}),
        status=500,
    )
