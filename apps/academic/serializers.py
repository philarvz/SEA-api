"""
Serializers for the Academic module.
Covers: Generation, Period, Group, Subject and auxiliary operations.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Generation, Period, Group, Subject, Unit, GroupTeacherAssignment
from .services import PeriodService
from apps.users.models import StudentProfile


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class GenerationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Generation
        fields = ['id_generation', 'year', 'total_levels', 'status']
        read_only_fields = ['id_generation']

    def validate_year(self, value):
        if value < 1900 or value > 2200:
            raise serializers.ValidationError('El año de generación no es válido.')
        return value

    def validate_total_levels(self, value):
        if value < 1:
            raise serializers.ValidationError('El número total de niveles debe ser mayor a 0.')
        return value


# ---------------------------------------------------------------------------
# Period
# ---------------------------------------------------------------------------

class PeriodSerializer(serializers.ModelSerializer):
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)

    class Meta:
        model = Period
        fields = ['id_period', 'period_name', 'start_date', 'end_date', 'status']
        read_only_fields = ['id_period', 'start_date', 'end_date']


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------

class GroupCreateSerializer(serializers.Serializer):
    """Input serializer for POST /groups/."""
    id_generation = serializers.IntegerField(required=True)
    group_letter = serializers.CharField(max_length=5, required=True)
    academic_level = serializers.IntegerField(min_value=1, required=False)
    status = serializers.BooleanField(default=True)

    def validate_id_generation(self, value):
        try:
            gen = Generation.objects.get(pk=value)
        except Generation.DoesNotExist:
            raise serializers.ValidationError('La generación especificada no existe.')
        if not gen.status:
            raise serializers.ValidationError('La generación especificada está inactiva.')
        # Store generation in context for cross-field validation
        self.context['_generation'] = gen
        return value

    def validate_group_letter(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        academic_level = attrs.get('academic_level')
        generation = self.context.get('_generation')
        if generation and academic_level and academic_level > generation.total_levels:
            raise serializers.ValidationError({
                'academic_level': f'El nivel académico no puede exceder {generation.total_levels} (total de niveles de la generación).'
            })
        return attrs


class GroupUpdateSerializer(serializers.Serializer):
    """Input serializer for PUT /groups/{id}/ — generation is immutable."""
    group_letter = serializers.CharField(max_length=5, required=True)
    academic_level = serializers.IntegerField(min_value=1, required=False)
    status = serializers.BooleanField(required=True)

    def validate_group_letter(self, value):
        return value.strip().upper()


class GroupSerializer(serializers.ModelSerializer):
    """Output serializer for read operations."""
    generation_year = serializers.IntegerField(source='id_generation.year', read_only=True)
    generation_total_levels = serializers.IntegerField(source='id_generation.total_levels', read_only=True)
    id_period = serializers.SerializerMethodField()
    period_info = serializers.SerializerMethodField()
    academic_level = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    assignments = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id_group', 'id_generation', 'generation_year',
            'generation_total_levels',
            'id_period', 'period_info',
            'group_letter', 'academic_level', 'students_count',
            'assignments', 'status',
        ]

    def _get_current_period(self):
        if not hasattr(self, '_cached_current_period'):
            self._cached_current_period = PeriodService.get_current_period()
        return self._cached_current_period

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_period_info(self, obj):
        current_period = self._get_current_period()
        if current_period:
            return current_period.period_name
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_id_period(self, obj):
        current_period = self._get_current_period()
        return current_period.pk if current_period else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_academic_level(self, obj):
        return PeriodService.sync_group_academic_level(obj)

    @extend_schema_field(serializers.IntegerField())
    def get_students_count(self, obj):
        return getattr(obj, 'students_count', obj.students.count())

    @extend_schema_field(serializers.ListField())
    def get_assignments(self, obj):
        try:
            assignments = obj.teacher_assignments.select_related(
                'teacher__user', 'subject'
            ).all()
            return [
                {
                    'id_assignment': a.pk,
                    'subject': {'id_subject': a.subject.pk, 'name': a.subject.name},
                    'teacher': {
                        'id_teacher': a.teacher.pk,
                        'full_name': a.teacher.user.full_name,
                        'email': a.teacher.user.email,
                    },
                }
                for a in assignments
            ]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id_unit', 'id_subject', 'unit_name', 'unit_number']
        read_only_fields = ['id_unit']


class SubjectSerializer(serializers.ModelSerializer):
    number_of_units = serializers.IntegerField(min_value=0, write_only=True, required=False)
    units = UnitSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = ['id_subject', 'name', 'level_number', 'number_of_units', 'units', 'status']
        read_only_fields = ['id_subject']

    def validate_level_number(self, value):
        if value < 1:
            raise serializers.ValidationError('El número de nivel debe ser mayor a 0.')
        return value


class TeacherSubjectSerializer(serializers.ModelSerializer):
    """Read-only serializer for teacher's assigned subjects (with nested units)."""
    units = UnitSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = ['id_subject', 'name', 'level_number', 'units', 'status']
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Shared / auxiliary
# ---------------------------------------------------------------------------

class GroupStatusUpdateSerializer(serializers.Serializer):
    """Generic serializer for logical activation / deactivation."""
    status = serializers.BooleanField(required=True)


class AssignStudentSerializer(serializers.Serializer):
    """Validates the student (StudentProfile pk) to be assigned to a group."""
    id_person = serializers.IntegerField(required=True)

    def validate_id_person(self, value):
        try:
            student = StudentProfile.objects.select_related('user').get(pk=value)
        except StudentProfile.DoesNotExist:
            raise serializers.ValidationError('El alumno especificado no existe.')
        if student.user.role != 'student':
            raise serializers.ValidationError(
                'El usuario especificado no tiene el rol de alumno.'
            )
        if not student.user.is_active:
            raise serializers.ValidationError('El alumno está inactivo.')
        return value


# ---------------------------------------------------------------------------
# Teacher assignment to group  (M:N through GroupTeacherAssignment)
# ---------------------------------------------------------------------------

class GroupTeacherAssignmentSerializer(serializers.Serializer):
    """Read output for a single group-teacher-subject assignment."""
    id_assignment = serializers.IntegerField()
    subject = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()

    def get_subject(self, obj):
        return {'id_subject': obj.subject.pk, 'name': obj.subject.name}

    def get_teacher(self, obj):
        return {
            'id_teacher': obj.teacher.pk,
            'full_name': obj.teacher.user.full_name,
            'email': obj.teacher.user.email,
        }


class CreateGroupTeacherAssignmentSerializer(serializers.Serializer):
    """
    Input for POST /groups/{pk}/assignments/.
    Assigns teacher_id to teach subject_id in this group.
    Business rules validated in the view:
      - subject must exist and its level_number == group.academic_level
      - teacher must have that subject assigned
    """
    teacher_id = serializers.IntegerField(required=True)
    subject_id = serializers.IntegerField(required=True)


class AvailableTeacherSerializer(serializers.Serializer):
    """Teacher eligible for assignment to a specific subject in a group."""
    id_teacher = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    subjects_at_level = serializers.ListField(child=serializers.CharField())


# ---------------------------------------------------------------------------
# Assignable groups (for exam assignment dialog selector)
# ---------------------------------------------------------------------------

class AssignableGroupSerializer(serializers.ModelSerializer):
    """
    Lightweight read-only serializer for groups available to be selected
    in the exam assignment dialog. Returns only display and identity fields;
    no assignment details or student lists are included.
    """
    generation_year = serializers.IntegerField(source='id_generation.year', read_only=True)
    generation_total_levels = serializers.IntegerField(source='id_generation.total_levels', read_only=True)
    id_period = serializers.SerializerMethodField()
    period_info = serializers.SerializerMethodField()
    academic_level = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id_group', 'id_generation', 'generation_year',
            'generation_total_levels', 'id_period', 'period_info',
            'group_letter', 'academic_level', 'status',
        ]

    def _get_current_period(self):
        if not hasattr(self, '_cached_current_period'):
            self._cached_current_period = PeriodService.get_current_period()
        return self._cached_current_period

    def get_id_period(self, obj):
        current_period = self._get_current_period()
        return current_period.pk if current_period else None

    def get_period_info(self, obj):
        current_period = self._get_current_period()
        return current_period.period_name if current_period else None

    def get_academic_level(self, obj):
        return PeriodService.sync_group_academic_level(obj)
