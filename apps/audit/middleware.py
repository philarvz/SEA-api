from django.db import connection


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
    Resets the PG session variable when the request finishes.

    The HTTP request is bound to thread-local storage by
    ``apps.core.middleware.RequestContextMiddleware`` (see ``get_current_request``).

    DRF authenticates lazily inside the view; the PG variable is set via
    ``apps.audit.authentication.AuditJWTAuthentication`` after successful JWT auth.

    Must be placed AFTER ``AuthenticationMiddleware`` and
    ``RequestContextMiddleware`` in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        finally:
            # Reset to anonymous so next request on same connection is clean
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_user', 'anonymous', false)"
                )
        return response
