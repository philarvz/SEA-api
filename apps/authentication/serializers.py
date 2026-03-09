from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """
    Serializer for login requests
    Validates email and password
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate_email(self, value):
        """Validate email format"""
        return value.lower().strip()
    
    class Meta:
        fields = ['email', 'password']


class TokenResponseSerializer(serializers.Serializer):
    """
    Serializer for token response
    Returns access and refresh tokens
    """
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = serializers.DictField(read_only=True)
    
    class Meta:
        fields = ['access', 'refresh', 'user']


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    Used for user data in token response
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'username', 'email']
