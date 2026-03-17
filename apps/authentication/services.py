"""
Authentication Service Layer
This module contains the business logic for authentication
Separated from views to maintain single responsibility principle
"""

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from apps.users.models import User


class AuthenticationService:
    """
    Service class for authentication operations
    Handles both mock and database authentication
    """

    @staticmethod
    def authenticate_user(email: str, password: str) -> dict:
        """
        Authenticate user based on USE_DATABASE setting

        Args:
            email: User email
            password: User password

        Returns:
            dict: User data and tokens

        Raises:
            AuthenticationFailed: If credentials are invalid
        """
        use_database = settings.USE_DATABASE

        if use_database:
            return AuthenticationService._authenticate_with_database(email, password)
        else:
            return AuthenticationService._authenticate_mock(email, password)

    @staticmethod
    def _authenticate_with_database(email: str, password: str) -> dict:
        """
        Authenticate user against database using Django's authenticate().

        Args:
            email: User email
            password: User password

        Returns:
            dict: User data and tokens

        Raises:
            AuthenticationFailed: If credentials are invalid
        """
        # Buscar usuario por email para obtener su username
        try:
            user_lookup = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed('Credenciales inválidas')

        # Autenticar con el sistema nativo de Django
        user = authenticate(username=user_lookup.username, password=password)
        if user is None:
            raise AuthenticationFailed('Credenciales inválidas')

        # Verificar estado del usuario
        if not user.status:
            raise AuthenticationFailed('Usuario inactivo')

        # Generar tokens JWT
        tokens = AuthenticationService._generate_tokens(user)

        # Obtener grupo si es estudiante
        group = None
        if user.role == 'student':
            try:
                group = user.student_profile.group_id
            except Exception:
                group = None

        return {
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
            'user': {
                'id': user.id_user,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'role': user.role,
                'group': group,
            }
        }

    @staticmethod
    def _authenticate_mock(email: str, password: str) -> dict:
        """
        Authenticate user with mock credentials.
        Used for testing when database is not available.

        Args:
            email: User email
            password: User password

        Returns:
            dict: Mock user data and tokens

        Raises:
            AuthenticationFailed: If credentials don't match mock credentials
        """
        mock_email = settings.MOCK_EMAIL
        mock_password = settings.MOCK_PASSWORD

        if email != mock_email or password != mock_password:
            raise AuthenticationFailed('Credenciales inválidas')

        mock_user = {
            'id': 1,
            'username': 'admin',
            'email': mock_email,
            'first_name': 'Admin',
            'last_name': 'Legacy Devs',
            'full_name': 'Admin Legacy Devs',
            'role': 'admin',
            'group': None,
        }

        tokens = AuthenticationService._generate_mock_tokens(mock_user)

        return {
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
            'user': mock_user
        }

    @staticmethod
    def _generate_tokens(user: User) -> dict:
        """
        Generate JWT tokens for an authenticated User instance.

        Args:
            user: Authenticated User instance

        Returns:
            dict: Access and refresh tokens
        """
        refresh = RefreshToken.for_user(user)
        # Claims adicionales para el frontend
        refresh['role'] = user.role
        refresh['email'] = user.email
        refresh['username'] = user.username
        refresh['full_name'] = user.full_name

        return {
            'refresh': refresh,
            'access': refresh.access_token,
        }

    @staticmethod
    def _generate_mock_tokens(user_data: dict) -> dict:
        """
        Generate JWT tokens for mock user.

        Args:
            user_data: Mock user data

        Returns:
            dict: Access and refresh tokens
        """
        refresh = RefreshToken()
        refresh['user_id'] = user_data['id']
        refresh['email'] = user_data['email']
        refresh['username'] = user_data['username']
        refresh['role'] = user_data.get('role', 'admin')

        return {
            'refresh': refresh,
            'access': refresh.access_token,
        }

    @staticmethod
    def refresh_token(refresh_token: str) -> dict:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            dict: New access token

        Raises:
            AuthenticationFailed: If refresh token is invalid
        """
        try:
            refresh = RefreshToken(refresh_token)
            return {
                'access': str(refresh.access_token)
            }
        except Exception:
            raise AuthenticationFailed('Token de refresco inválido')
