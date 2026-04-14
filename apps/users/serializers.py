"""
Users module serializers
Covers: user registration input validation and response shape.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from apps.academic.services import PeriodService
from utils.sanitizers import sanitize_name, contains_html

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration — Input
# ---------------------------------------------------------------------------

class RegisterUserSerializer(serializers.Serializer):

    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    matricula = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
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
        if not value:
            return ''
        value = value.strip()
        if User.objects.filter(matricula=value).exists():
            raise serializers.ValidationError('La matrícula ya está registrada.')
        return value

    def validate_first_name(self, value: str) -> str:
        if contains_html(value):
            raise serializers.ValidationError('El nombre no debe contener HTML.')
        value = sanitize_name(value)
        if not value:
            raise serializers.ValidationError('El nombre es requerido.')
        return value

    def validate_last_name(self, value: str) -> str:
        if contains_html(value):
            raise serializers.ValidationError('El apellido no debe contener HTML.')
        value = sanitize_name(value)
        if not value:
            raise serializers.ValidationError('El apellido es requerido.')
        return value

    # -----------------------------------------------------------------
    # Cross-field validations
    # -----------------------------------------------------------------

    def validate(self, attrs: dict) -> dict:
        role = attrs.get('role')
        id_group = attrs.get('id_group')
        subject_ids = attrs.get('subject_ids', [])
        matricula = attrs.get('matricula')

        # Validar que estudiantes y docentes tengan matrícula
        if role in ['student', 'teacher'] and not matricula:
            raise serializers.ValidationError(
                {'matricula': 'La matrícula es requerida para estudiantes y docentes.'}
            )

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
# Update User — Input
# ---------------------------------------------------------------------------

class UpdateUserSerializer(serializers.Serializer):
    """Serializer para actualizar datos de un usuario existente.
    Note: El rol no puede ser modificado después de la creación del usuario."""

    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    matricula = serializers.CharField(max_length=20, required=False)
    status = serializers.BooleanField(required=False)

    # Optional — only used depending on role
    id_group = serializers.IntegerField(required=False, allow_null=True)
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        help_text='IDs de materias asignadas (solo docentes).',
    )

    # -----------------------------------------------------------------
    # Field-level validations
    # -----------------------------------------------------------------

    def validate_email(self, value: str) -> str:
        """Validar que el email no esté en uso por otro usuario"""
        value = value.lower().strip()
        user_id = self.context.get('user_id')
        if User.objects.filter(email__iexact=value).exclude(id_user=user_id).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value

    def validate_matricula(self, value: str) -> str:
        """Validar que la matrícula no esté en uso por otro usuario"""
        if not value:
            return ''
        value = value.strip()
        user_id = self.context.get('user_id')
        if User.objects.filter(matricula=value).exclude(id_user=user_id).exists():
            raise serializers.ValidationError('La matrícula ya está registrada.')
        return value

    def validate_first_name(self, value: str) -> str:
        if contains_html(value):
            raise serializers.ValidationError('El nombre no debe contener HTML.')
        value = sanitize_name(value)
        if not value:
            raise serializers.ValidationError('El nombre es requerido.')
        return value

    def validate_last_name(self, value: str) -> str:
        if contains_html(value):
            raise serializers.ValidationError('El apellido no debe contener HTML.')
        value = sanitize_name(value)
        if not value:
            raise serializers.ValidationError('El apellido es requerido.')
        return value

    # -----------------------------------------------------------------
    # Cross-field validations
    # -----------------------------------------------------------------

    def validate(self, attrs: dict) -> dict:
        id_group = attrs.get('id_group')
        subject_ids = attrs.get('subject_ids')

        # Validar grupo si se proporciona
        if id_group is not None:
            from apps.academic.models import Group
            if not Group.objects.filter(pk=id_group, status=True).exists():
                raise serializers.ValidationError(
                    {'id_group': 'El grupo especificado no existe o está inactivo.'}
                )

        # Validar materias si se proporcionan
        if subject_ids is not None and len(subject_ids) > 0:
            from apps.academic.models import Subject
            found = Subject.objects.filter(pk__in=subject_ids, status=True).count()
            if found != len(subject_ids):
                raise serializers.ValidationError(
                    {'subject_ids': 'Una o más materias especificadas no existen o están inactivas.'}
                )

        return attrs


# ---------------------------------------------------------------------------
# Status Update — Input
# ---------------------------------------------------------------------------

class StatusUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar el estado de un usuario (activo/inactivo)"""
    status = serializers.BooleanField(required=True)


# ---------------------------------------------------------------------------
# Registration — Output
# ---------------------------------------------------------------------------

class GroupSummarySerializer(serializers.Serializer):
    """Minimal group representation embedded in the user response."""
    id_group = serializers.IntegerField()
    group_letter = serializers.CharField()
    academic_level = serializers.IntegerField()
    generation_year = serializers.IntegerField()


class SubjectSummarySerializer(serializers.Serializer):
    """Minimal subject representation embedded in the teacher response."""
    id_subject = serializers.IntegerField()
    name = serializers.CharField()


class UserResponseSerializer(serializers.ModelSerializer):

    full_name = serializers.CharField(read_only=True)
    group = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()
    teaching_groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id_user', 'email', 'username', 'matricula',
            'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'date_joined',
            'group', 'subjects', 'teaching_groups',
        ]
        read_only_fields = fields

    @extend_schema_field(GroupSummarySerializer(allow_null=True))
    def get_group(self, obj: User):
        if obj.role == 'student':
            try:
                profile = obj.student_profile
                if profile.group:
                    calculated_level = PeriodService.sync_group_academic_level(profile.group)
                    return {
                        'id_group': profile.group.pk,
                        'group_letter': profile.group.group_letter,
                        'academic_level': calculated_level,
                        'generation_year': profile.group.id_generation.year,
                    }
            except Exception:
                pass
        return None

    @extend_schema_field(SubjectSummarySerializer(many=True))
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

    @extend_schema_field(GroupSummarySerializer(many=True))
    def get_teaching_groups(self, obj: User):
        """Retorna los grupos donde el docente imparte clase (sin duplicados)."""
        if obj.role == 'teacher':
            try:
                seen = set()
                result = []
                for assignment in obj.teacher_profile.group_assignments.all():
                    group = assignment.group
                    if group.pk not in seen:
                        seen.add(group.pk)
                        calculated_level = PeriodService.sync_group_academic_level(group)
                        result.append({
                            'id_group': group.pk,
                            'group_letter': group.group_letter,
                            'academic_level': calculated_level,
                            'generation_year': group.id_generation.year,
                        })
                return result
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
    teaching_groups = serializers.SerializerMethodField()

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
            'teaching_groups',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_status_display(self, obj: User):
        """Retorna el estado en formato legible"""
        return 'Activo' if obj.status else 'Inactivo'

    @extend_schema_field(GroupSummarySerializer(allow_null=True))
    def get_group(self, obj: User):
        """Retorna información del grupo si es estudiante"""
        if obj.role == 'student':
            try:
                profile = obj.student_profile
                if profile.group:
                    calculated_level = PeriodService.sync_group_academic_level(profile.group)
                    return {
                        'id_group': profile.group.pk,
                        'group_letter': profile.group.group_letter,
                        'academic_level': calculated_level,
                        'generation_year': profile.group.id_generation.year,
                    }
            except Exception:
                pass
        return None

    @extend_schema_field(SubjectSummarySerializer(many=True))
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

    @extend_schema_field(GroupSummarySerializer(many=True))
    def get_teaching_groups(self, obj: User):
        """Retorna los grupos donde el docente imparte clase (sin duplicados)."""
        if obj.role == 'teacher':
            try:
                seen = set()
                result = []
                for assignment in obj.teacher_profile.group_assignments.all():
                    group = assignment.group
                    if group.pk not in seen:
                        seen.add(group.pk)
                        calculated_level = PeriodService.sync_group_academic_level(group)
                        result.append({
                            'id_group': group.pk,
                            'group_letter': group.group_letter,
                            'academic_level': calculated_level,
                            'generation_year': group.id_generation.year,
                        })
                return result
            except Exception:
                pass
        return []


# ---------------------------------------------------------------------------
# Password Recovery Serializers
# ---------------------------------------------------------------------------

class RequestPasswordResetSerializer(serializers.Serializer):
    """Serializer para solicitar código de recuperación de contraseña"""
    email = serializers.EmailField(required=True, max_length=254)

    def validate_email(self, value: str) -> str:
        # Only normalize — existence check is deferred to the service layer
        # to avoid leaking whether an account exists (CWE-204).
        return value.lower().strip()


class VerifyResetCodeSerializer(serializers.Serializer):
    """Serializer para verificar código de recuperación"""
    email = serializers.EmailField(required=True)
    code = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_email(self, value: str) -> str:
        return value.lower().strip()

    def validate_code(self, value: str) -> str:
        return value.strip().upper()


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer para restablecer contraseña con código verificado"""
    # Constantes para nombres de campos
    FIELD_NEW_PWD = 'new_password'
    FIELD_CONFIRM_PWD = 'confirm_password'
    MSG_MISMATCH = 'Las claves no coinciden.'
    
    email = serializers.EmailField(required=True)
    code = serializers.CharField(min_length=6, max_length=6, required=True)
    new_password = serializers.CharField(min_length=8, max_length=128, required=True)
    confirm_password = serializers.CharField(min_length=8, max_length=128, required=True)

    def validate_email(self, value: str) -> str:
        return value.lower().strip()

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs: dict) -> dict:
        if attrs[self.FIELD_NEW_PWD] != attrs[self.FIELD_CONFIRM_PWD]:
            raise serializers.ValidationError(
                {self.FIELD_CONFIRM_PWD: self.MSG_MISMATCH}
            )
        return attrs
