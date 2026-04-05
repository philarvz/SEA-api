"""
Middleware that binds ``request`` to thread-local storage for the request lifecycle.
"""

from apps.core.thread_local import clear_current_request, set_current_request


class RequestContextMiddleware:
    """
    Stores the current ``HttpRequest`` in thread-local storage for the duration
    of the request, so ``get_current_user()`` can resolve ``request.user``
    from model code (including after DRF authenticates the JWT in the view).

    Place immediately after ``AuthenticationMiddleware``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            clear_current_request()
