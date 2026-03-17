"""
Custom permission classes for the Academic module.
"""

from rest_framework.permissions import BasePermission


class IsTeacherOrAdmin(BasePermission):
    """
    Grants access only to authenticated users with the 'teacher' or 'admin' role.
    The role claim is read directly from the JWT access token payload.
    """
    message = 'Acceso restringido a docentes y administradores.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Role is embedded as a custom claim in the JWT token;
        # simplejwt TokenUser delegates attribute access to the token payload.
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')
        return role in ('teacher', 'admin')
