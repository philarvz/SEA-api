import threading

from django.db import connection


_request_store = threading.local()


def get_current_request():
    """Return the current request from thread-local storage."""
    return getattr(_request_store, 'request', None)


def set_audit_user(user_id=None):
    """
    Set the PostgreSQL session variable "app.current_user".

    Uses set_config() to avoid reserved-keyword issues with SET.
    Third arg false = session-level (persists in autocommit mode).
    The middleware resets it to 'anonymous' when the request finishes.
    """
    if user_id is None:
        user_id = 'anonymous'
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_user', %s, false)",
            [str(user_id)],
        )


class AuditUserMiddleware:
    """
    1. Stores the request in thread-local so set_audit_user() can read it.
    2. Resets the PG variable to 'anonymous' when the request finishes,
       preventing user leakage across requests on the same connection.

    DRF authenticates lazily inside the view, so the PG variable is
    set via apps.audit.authentication.AuditJWTAuthentication — a thin
    wrapper around JWTStatelessUserAuthentication that calls
    set_audit_user() right after successful authentication.

    Must be placed AFTER AuthenticationMiddleware in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request_store.request = request
        try:
            response = self.get_response(request)
        finally:
            _request_store.request = None
            # Reset to anonymous so next request on same connection is clean
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_user', 'anonymous', false)"
                )
        return response
