"""
Authentication Views
Handles HTTP requests for authentication endpoints
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse
from loguru import logger

from .serializers import LoginSerializer, TokenResponseSerializer, ChangePasswordSerializer
from .services import AuthenticationService
from utils.responses import success_response, error_response


class LoginView(APIView):
    """
    Authenticate user and return JWT tokens
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        request=LoginSerializer,
        responses={
            200: TokenResponseSerializer,
            401: OpenApiResponse(description='Credenciales inválidas'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description='Autenticar usuario con email y contraseña',
        tags=['Authentication']
    )
    def post(self, request):
        """
        Authenticate user with email and password
        
        Request body:
            - email: User email
            - password: User password
            
        Response:
            - access: Access token
            - refresh: Refresh token
            - user: User data
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Use authentication service for business logic
            result = AuthenticationService.authenticate_user(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except AuthenticationFailed as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {'error': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TokenRefreshView(APIView):
    """
    Refresh access token using refresh token
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        request={'type': 'object', 'properties': {'refresh': {'type': 'string'}}},
        responses={
            200: {'type': 'object', 'properties': {'access': {'type': 'string'}}},
            400: OpenApiResponse(description='Token de refresco requerido'),
            401: OpenApiResponse(description='Token inválido'),
        },
        description='Refrescar token de acceso',
        tags=['Authentication']
    )
    def post(self, request):
        """
        Refresh access token
        
        Request body:
            - refresh: Refresh token
            
        Response:
            - access: New access token
        """
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response(
                {'error': 'Token de refresco requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use authentication service for business logic
            result = AuthenticationService.refresh_token(refresh_token)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except AuthenticationFailed as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {'error': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """
    Health check endpoint for authentication service
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}, 'mode': {'type': 'string'}}}},
        description='Verificar estado del servicio de autenticación',
        tags=['Health']
    )
    def get(self, request):
        """
        Check if authentication service is running
        
        Response:
            - status: Service status
            - mode: Authentication mode (database or mock)
        """
        from django.conf import settings
        
        return Response({
            'status': 'ok',
            'service': 'authentication',
            'mode': 'database' if settings.USE_DATABASE else 'mock'
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """
    Vista para cambiar la contraseña del usuario autenticado.
    Requiere autenticación JWT.
    El payload debe estar cifrado con AES-256-CBC.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cambiar contraseña',
        tags=['Authentication'],
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description='Contraseña cambiada exitosamente'),
            400: OpenApiResponse(description='Datos inválidos'),
            401: OpenApiResponse(description='Contraseña actual incorrecta o no autenticado'),
        },
        description=(
            'Permite al usuario autenticado cambiar su contraseña. '
            'El payload debe estar cifrado usando AES-256-CBC. '
            'Campos requeridos (cifrados): current_password, new_password, confirm_password.'
        ),
    )
    def post(self, request):
        # Obtener el usuario real de la base de datos (no el TokenUser)
        from apps.users.models import User
        try:
            user = User.objects.get(id_user=request.user.id)
        except User.DoesNotExist:
            logger.error('User not found in database | user_id={}', request.user.id)
            return error_response(
                'Usuario no encontrado.',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ChangePasswordSerializer(data=request.data, context={'user': user})
        
        if not serializer.is_valid():
            logger.warning(
                'Password change validation failed | user={} errors={}',
                user.username, serializer.errors
            )
            return error_response('Datos inválidos.', serializer.errors)
        
        # Obtener datos descifrados del contexto
        decrypted_data = serializer.context.get('decrypted_data', {})
        current_password = decrypted_data.get('current_password')
        new_password = decrypted_data.get('new_password')
        
        # Verificar que la contraseña actual sea correcta
        if not user.check_password(current_password):
            logger.warning(
                'Password change failed: incorrect current password | user={}',
                user.username
            )
            return error_response(
                'La contraseña actual es incorrecta.',
                {'current_password': 'Contraseña incorrecta.'},
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Cambiar la contraseña
        user.set_password(new_password)
        user.save()
        
        logger.info('Password changed successfully | user={}', user.username)
        
        return success_response(
            {'message': 'Contraseña cambiada exitosamente.'},
            'Tu contraseña ha sido actualizada correctamente.'
        )
