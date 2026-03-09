"""
Authentication Views
Handles HTTP requests for authentication endpoints
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import LoginSerializer, TokenResponseSerializer
from .services import AuthenticationService


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
