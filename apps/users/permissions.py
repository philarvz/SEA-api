"""
Custom permission classes for the Users module.
"""

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Grants access only to authenticated users with the 'admin' role.

    Works with both JWTStatelessUserAuthentication (reads from token claims)
    and standard JWTAuthentication (reads from DB user instance).
    """

    message = 'Acceso restringido. Se requiere rol de administrador.'

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        # JWTStatelessUserAuthentication exposes claims via .role attribute
        # or via request.auth payload as fallback.
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')
        return role == 'admin'
