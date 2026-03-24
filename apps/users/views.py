"""
Users module views
Covers: user registration (admin-only).
"""

from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .permissions import IsAdmin
from .serializers import RegisterUserSerializer, UserResponseSerializer
from .services import UserRegistrationService
from utils.responses import success_response, error_response


class RegisterUserView(APIView):
    """
    POST /api/users/register/

    Register a new user in the system.
    Restricted to administrators.

    On success:
        - Creates the User + role-specific profile in a DB transaction.
        - Sends a welcome e-mail with the generated credentials.
        - Returns the created user data (password is NOT returned).
    """

    permission_classes = [IsAdmin]

    @extend_schema(
        summary='Registrar nuevo usuario',
        tags=['Usuarios'],
        request=RegisterUserSerializer,
        responses={
            201: UserResponseSerializer,
            400: OpenApiResponse(description='Datos de entrada inválidos'),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Crea un nuevo usuario (alumno, docente o administrador). '
            'Solo los administradores pueden acceder. '
            'La contraseña se genera automáticamente y se envía al correo del usuario.'
        ),
    )
    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                'User registration rejected | errors={}', serializer.errors
            )
            return error_response('Datos inválidos.', serializer.errors)

        try:
            user, _ = UserRegistrationService.register_user(serializer.validated_data)
            return success_response(
                UserResponseSerializer(user).data,
                'Usuario registrado exitosamente. Se ha enviado un correo con las credenciales.',
                status.HTTP_201_CREATED,
            )
        except Exception as exc:
            logger.error('Error registering user | {}', exc)
            return error_response(
                'Error interno al registrar el usuario.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
