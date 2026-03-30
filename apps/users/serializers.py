"""
Users module serializers
Covers: user registration input validation and response shape.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration — Input
# ---------------------------------------------------------------------------

class RegisterUserSerializer(serializers.Serializer):

    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    matricula = serializers.CharField(max_length=20, required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    # Status siempre True, se envía pero no se usa desde el cliente
    status = serializers.BooleanField(default=True, required=False)

    # Optional — only used depending on role
    id_group = serializers.IntegerField(required=False, allow_null=True)
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='IDs de materias asignadas (solo docentes).',
    )

    # -----------------------------------------------------------------
    # Field-level validations
    # -----------------------------------------------------------------

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value

    def validate_matricula(self, value: str) -> str:
        value = value.strip()
        if User.objects.filter(matricula=value).exists():
            raise serializers.ValidationError('La matrícula ya está registrada.')
        return value

    def validate_first_name(self, value: str) -> str:
        return value.strip()

    def validate_last_name(self, value: str) -> str:
        return value.strip()

    # -----------------------------------------------------------------
    # Cross-field validations
    # -----------------------------------------------------------------

    def validate(self, attrs: dict) -> dict:
        role = attrs.get('role')
        id_group = attrs.get('id_group')
        subject_ids = attrs.get('subject_ids', [])

        if role == 'student' and id_group:
            from apps.academic.models import Group
            if not Group.objects.filter(pk=id_group, status=True).exists():
                raise serializers.ValidationError(
                    {'id_group': 'El grupo especificado no existe o está inactivo.'}
                )

        if role == 'teacher' and subject_ids:
            from apps.academic.models import Subject
            found = Subject.objects.filter(pk__in=subject_ids, status=True).count()
            if found != len(subject_ids):
                raise serializers.ValidationError(
                    {'subject_ids': 'Una o más materias especificadas no existen o están inactivas.'}
                )

        return attrs


# ---------------------------------------------------------------------------
# Registration — Output
# ---------------------------------------------------------------------------

class GroupSummarySerializer(serializers.Serializer):
    """Minimal group representation embedded in the user response."""
    id_group = serializers.IntegerField()
    group_letter = serializers.CharField()
    academic_level = serializers.IntegerField()


class SubjectSummarySerializer(serializers.Serializer):
    """Minimal subject representation embedded in the teacher response."""
    id_subject = serializers.IntegerField()
    name = serializers.CharField()


class UserResponseSerializer(serializers.ModelSerializer):

    full_name = serializers.CharField(read_only=True)
    group = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id_user', 'email', 'username', 'matricula',
            'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'date_joined',
            'group', 'subjects',
        ]
        read_only_fields = fields

    def get_group(self, obj: User):
        if obj.role == 'student':
            try:
                profile = obj.student_profile
                if profile.group:
                    return {
                        'id_group': profile.group.pk,
                        'group_letter': profile.group.group_letter,
                        'academic_level': profile.group.academic_level,
                    }
            except Exception:
                pass
        return None

    def get_subjects(self, obj: User):
        if obj.role == 'teacher':
            try:
                return [
                    {'id_subject': s.pk, 'name': s.name}
                    for s in obj.teacher_profile.subjects.all()
                ]
            except Exception:
                pass
        return []


# ---------------------------------------------------------------------------
# User List — Output
# ---------------------------------------------------------------------------

class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    group = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id_user',
            'matricula',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'role',
            'status',
            'status_display',
            'is_active',
            'date_joined',
            'group',
            'subjects',
        ]
        read_only_fields = fields

    def get_status_display(self, obj: User):
        """Retorna el estado en formato legible"""
        return 'Activo' if obj.status else 'Inactivo'

    def get_group(self, obj: User):
        """Retorna información del grupo si es estudiante"""
        if obj.role == 'student':
            try:
                profile = obj.student_profile
                if profile.group:
                    return {
                        'id_group': profile.group.pk,
                        'group_letter': profile.group.group_letter,
                        'academic_level': profile.group.academic_level,
                    }
            except Exception:
                pass
        return None

    def get_subjects(self, obj: User):
        """Retorna lista de materias si es docente"""
        if obj.role == 'teacher':
            try:
                return [
                    {'id_subject': s.pk, 'name': s.name}
                    for s in obj.teacher_profile.subjects.all()
                ]
            except Exception:
                pass
        return []
