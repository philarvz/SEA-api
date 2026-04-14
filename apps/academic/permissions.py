"""
Custom permission classes for the Academic module.
"""

from rest_framework.permissions import BasePermission


def get_user_role(request):
    """Extract the role claim from the authenticated user / JWT token."""
    role = getattr(request.user, 'role', None)
    if role is None and request.auth is not None:
        role = request.auth.get('role')
    return role


class IsTeacherOrAdmin(BasePermission):
    """
    Grants access only to authenticated users with the 'teacher' or 'admin' role.
    The role claim is read directly from the JWT access token payload.
    """
    message = 'Acceso restringido a docentes y administradores.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request) in ('teacher', 'admin')


class IsAdmin(BasePermission):
    """
    Grants access only to authenticated users with the 'admin' role.
    """
    message = 'Acceso restringido a administradores.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request) == 'admin'


class IsStudent(BasePermission):
    """
    Grants access only to authenticated users with the 'student' role.
    The role claim is read directly from the JWT access token payload.
    """
    message = 'Acceso restringido a alumnos.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request) == 'student'
