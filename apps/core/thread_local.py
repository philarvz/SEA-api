"""
Thread-local HTTP request storage for request-scoped helpers.

Used by ``RequestContextMiddleware`` so code running during a request
(including ORM ``save()`` after DRF/JWT authentication) can resolve
``request.user`` via ``get_current_user()``.
"""

from __future__ import annotations

import threading
from typing import Any

from django.contrib.auth import get_user_model

_local = threading.local()


def set_current_request(request: Any | None) -> None:
    """Bind ``request`` to the current thread (or clear if ``None``)."""
    if request is None:
        clear_current_request()
    else:
        _local.request = request


def clear_current_request() -> None:
    if hasattr(_local, 'request'):
        delattr(_local, 'request')


def get_current_request() -> Any | None:
    """Return the current ``HttpRequest`` for this thread, or ``None``."""
    return getattr(_local, 'request', None)


def get_current_user():
    """
    Return the authenticated ``User`` model instance for this thread, or ``None``.

    JWT (e.g. SimpleJWT ``TokenUser``) is resolved to a real DB row so ForeignKeys
    like ``modified_by`` accept the value.

    Resolved at call time from the thread-local request so authentication inside
    DRF views is visible when models are saved.
    """
    request = get_current_request()
    if request is None:
        return None
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None

    User = get_user_model()
    if isinstance(user, User):
        return user

    pk = getattr(user, 'pk', None)
    if pk is None:
        return None
    try:
        return User.objects.get(pk=pk)
    except User.DoesNotExist:
        return None
