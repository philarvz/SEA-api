from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication

from .middleware import set_audit_user


class AuditJWTAuthentication(JWTStatelessUserAuthentication):
    """
    Thin wrapper around JWTStatelessUserAuthentication that sets the
    PostgreSQL session variable "app.current_user" immediately after
    successful authentication — before any ORM write in the view.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _ = result
            set_audit_user(user.pk)
        return result
