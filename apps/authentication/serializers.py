from rest_framework import serializers
from apps.users.models import User
from utils.crypto import crypto_service

# Constantes para mensajes de error
MSG_CURRENT_CREDENTIAL_REQUIRED = 'La clave actual es requerida.'
MSG_NEW_CREDENTIAL_REQUIRED = 'La nueva clave es requerida.'
MSG_CREDENTIAL_MIN_LENGTH = 'La nueva clave debe tener al menos 8 caracteres.'
MSG_CREDENTIALS_NOT_MATCH = 'Las claves no coinciden.'
MSG_CREDENTIAL_MUST_BE_DIFFERENT = 'La nueva clave debe ser diferente a la actual.'


class LoginSerializer(serializers.Serializer):
    """
    Serializer for login requests.
    Validates email and user credentials.
    """
    email = serializers.EmailField(required=True, max_length=254)
    password = serializers.CharField(required=True, write_only=True, max_length=128)

    def validate_email(self, value):
        """Normalize email to lowercase"""
        return value.lower().strip()

    class Meta:
        fields = ['email', 'password']


class TokenRefreshRequestSerializer(serializers.Serializer):
    """Serializer for token refresh requests."""
    refresh = serializers.CharField(required=True, max_length=1024, help_text='JWT refresh token')


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Serializer for token refresh responses."""
    access = serializers.CharField(read_only=True)


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


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer para cambio de clave de acceso.
    Recibe un payload cifrado que contiene:
    - current_password: Clave actual del usuario
    - new_password: Nueva clave
    - confirm_password: Confirmación de la nueva clave
    """
    encrypted_data = serializers.CharField(required=True, write_only=True, max_length=2048)

    def validate_encrypted_data(self, value):
        """Descifra y valida el payload"""
        try:
            # Descifrar datos
            decrypted = crypto_service.decrypt_data(value)
            
            # Validar que contenga los campos requeridos
            required_fields = ['current_password', 'new_password', 'confirm_password']
            for field in required_fields:
                if field not in decrypted:
                    raise serializers.ValidationError(f'El campo {field} es requerido.')
            
            # Guardar datos descifrados en el contexto para usarlos después
            self.context['decrypted_data'] = decrypted
            
            return value
        except ValueError:
            raise serializers.ValidationError('Datos cifrados inválidos o corruptos.')
    
    def validate(self, attrs):
        """Validaciones cruzadas de las claves de acceso"""
        decrypted = self.context.get('decrypted_data', {})
        
        current_clave = decrypted.get('current_password', '')
        nueva_clave = decrypted.get('new_password', '')
        confirmar_clave = decrypted.get('confirm_password', '')
        
        # Validar que las claves no estén vacías
        if not current_clave:
            raise serializers.ValidationError({'current_password': MSG_CURRENT_CREDENTIAL_REQUIRED})  # NOSONAR
        
        if not nueva_clave:
            raise serializers.ValidationError({'new_password': MSG_NEW_CREDENTIAL_REQUIRED})  # NOSONAR
        
        # Validar longitud máxima de la nueva clave
        if len(nueva_clave) > 128:
            raise serializers.ValidationError({'new_password': 'La clave no puede exceder 128 caracteres.'})  # NOSONAR

        # Validar longitud mínima de la nueva clave
        if len(nueva_clave) < 8:
            raise serializers.ValidationError({'new_password': MSG_CREDENTIAL_MIN_LENGTH})  # NOSONAR
        
        # Validar que las claves coincidan
        if nueva_clave != confirmar_clave:
            raise serializers.ValidationError({'confirm_password': MSG_CREDENTIALS_NOT_MATCH})  # NOSONAR
        
        # Validar que la nueva clave sea diferente a la actual
        if current_clave == nueva_clave:
            raise serializers.ValidationError({'new_password': MSG_CREDENTIAL_MUST_BE_DIFFERENT})  # NOSONAR
        
        return attrs
