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


class IsAdminOrTeacherStudentGroupRead(BasePermission):
    """
    Access policy for user listing endpoint:
    - Admin: full access.
    - Teacher: GET access only when querying students scoped by group.
    """

    message = 'Acceso restringido. Solo administradores o consulta de alumnos por grupo para docentes.'

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')

        if role == 'admin':
            return True

        if role != 'teacher' or request.method != 'GET':
            return False

        requested_role = request.query_params.get('role')
        group_scope = request.query_params.get('group_id') or request.query_params.get('group')
        return requested_role == 'student' and bool(group_scope)
