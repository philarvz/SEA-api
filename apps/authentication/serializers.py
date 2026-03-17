from rest_framework import serializers
from apps.users.models import User


class LoginSerializer(serializers.Serializer):
    """
    Serializer for login requests.
    Validates email and password.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate_email(self, value):
        """Normalize email to lowercase"""
        return value.lower().strip()

    class Meta:
        fields = ['email', 'password']


class TokenResponseSerializer(serializers.Serializer):
    """
    Serializer for token response.
    Returns access and refresh tokens plus user data.
    """
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = serializers.DictField(read_only=True)

    class Meta:
        fields = ['access', 'refresh', 'user']


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    Used for user data in token response and other endpoints.
    Keeps the same output fields consumidos por el frontend.
    """
    full_name = serializers.CharField(read_only=True)
    group = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id_user', 'username', 'email',
            'first_name', 'last_name', 'full_name',
            'role', 'group',
        ]
        read_only_fields = ['id_user', 'username', 'email']

    def get_group(self, obj):
        """Retorna el id del grupo si el usuario es estudiante"""
        if obj.role == 'student':
            try:
                return obj.student_profile.group_id
            except Exception:
                return None
        return None
