from rest_framework import serializers
from apps.users.models import User
from utils.crypto import crypto_service


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


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer para cambio de contraseña.
    Recibe un payload cifrado que contiene:
    - current_password: Contraseña actual del usuario
    - new_password: Nueva contraseña
    - confirm_password: Confirmación de la nueva contraseña
    """
    encrypted_data = serializers.CharField(required=True, write_only=True)

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
        except ValueError as e:
            raise serializers.ValidationError('Datos cifrados inválidos o corruptos.')
    
    def validate(self, attrs):
        """Validaciones cruzadas de las contraseñas"""
        decrypted = self.context.get('decrypted_data', {})
        
        current_password = decrypted.get('current_password', '')
        new_password = decrypted.get('new_password', '')
        confirm_password = decrypted.get('confirm_password', '')
        
        # Validar que las contraseñas no estén vacías
        if not current_password:
            raise serializers.ValidationError({'current_password': 'La contraseña actual es requerida.'})
        
        if not new_password:
            raise serializers.ValidationError({'new_password': 'La nueva contraseña es requerida.'})
        
        # Validar longitud mínima de la nueva contraseña
        if len(new_password) < 8:
            raise serializers.ValidationError({'new_password': 'La nueva contraseña debe tener al menos 8 caracteres.'})
        
        # Validar que las contraseñas coincidan
        if new_password != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Las contraseñas no coinciden.'})
        
        # Validar que la nueva contraseña sea diferente a la actual
        if current_password == new_password:
            raise serializers.ValidationError({'new_password': 'La nueva contraseña debe ser diferente a la actual.'})
        
        return attrs
