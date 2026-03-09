"""
Authentication Service Layer
This module contains the business logic for authentication
Separated from views to maintain single responsibility principle
"""

from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from apps.users.models import Person, UserAccount


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
        Authenticate user against database using Person and UserAccount tables
        
        Args:
            email: User email
            password: User password
            
        Returns:
            dict: User data and tokens
            
        Raises:
            AuthenticationFailed: If credentials are invalid
        """
        try:
            # Find person by email
            person = Person.objects.select_related('user_account').get(email=email)
        except Person.DoesNotExist:
            raise AuthenticationFailed('Credenciales inválidas')
        
        # Check if user account exists
        try:
            user_account = person.user_account
        except UserAccount.DoesNotExist:
            raise AuthenticationFailed('Usuario no tiene cuenta activa')
        
        # Verify password
        if not check_password(password, user_account.password_hash):
            raise AuthenticationFailed('Credenciales inválidas')
        
        # Check if user is active
        if not user_account.status or not person.status:
            raise AuthenticationFailed('Usuario inactivo')
        
        # Generate tokens
        tokens = AuthenticationService._generate_tokens_for_person(person, user_account)
        
        return {
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
            'user': {
                'id': person.id_person,
                'username': user_account.username,
                'email': person.email,
                'first_name': person.first_name,
                'last_name': person.last_name,
                'full_name': person.full_name,
                'role': user_account.role,
            }
        }
    
    @staticmethod
    def _authenticate_mock(email: str, password: str) -> dict:
        """
        Authenticate user with mock credentials
        Used for testing when database is not available
        
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
        
        # Create mock user data
        mock_user = {
            'id': 1,
            'username': 'admin',
            'email': mock_email,
            'first_name': 'Admin',
            'last_name': 'Legacy Devs',
        }
        
        # Generate tokens for mock user
        tokens = AuthenticationService._generate_mock_tokens(mock_user)
        
        return {
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
            'user': mock_user
        }
    
    @staticmethod
    def _generate_tokens_for_person(person: Person, user_account: UserAccount) -> dict:
        """
        Generate JWT tokens for authenticated user (Person + UserAccount)
        
        Args:
            person: Person instance
            user_account: UserAccount instance
            
        Returns:
            dict: Access and refresh tokens
        """
        refresh = RefreshToken()
        refresh['user_id'] = person.id_person
        refresh['email'] = person.email
        refresh['username'] = user_account.username
        refresh['role'] = user_account.role
        refresh['full_name'] = person.full_name
        
        return {
            'refresh': refresh,
            'access': refresh.access_token,
        }
    
    @staticmethod
    def _generate_mock_tokens(user_data: dict) -> dict:
        """
        Generate JWT tokens for mock user
        
        Args:
            user_data: Mock user data
            
        Returns:
            dict: Access and refresh tokens
        """
        from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
        
        # Create a temporary token with user data
        refresh = RefreshToken()
        refresh['user_id'] = user_data['id']
        refresh['email'] = user_data['email']
        refresh['username'] = user_data['username']
        
        access = refresh.access_token
        
        return {
            'refresh': refresh,
            'access': access,
        }
    
    @staticmethod
    def refresh_token(refresh_token: str) -> dict:
        """
        Refresh access token using refresh token
        
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
        except Exception as e:
            raise AuthenticationFailed('Token de refresco inválido')
