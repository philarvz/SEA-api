from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication
from drf_spectacular.extensions import OpenApiAuthenticationExtension

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


class AuditJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Extension for drf-spectacular to properly recognize AuditJWTAuthentication
    as a JWT Bearer authentication scheme in Swagger UI.
    """
    target_class = 'apps.audit.authentication.AuditJWTAuthentication'
    name = 'bearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'JWT Authorization header using the Bearer scheme. Example: "Bearer {token}"'
        }
