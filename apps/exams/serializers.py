"""
Serializers for the Exams module.
Covers: Exam CRUD operations with academic validation.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import Exam, ExamAssignment
from apps.academic.models import Subject, Unit, Group


# ---------------------------------------------------------------------------
# Student grades per group (for the grades view)
# ---------------------------------------------------------------------------

STATUS_LABELS = dict(ExamAssignment.ASSIGNMENT_STATUS_CHOICES)


class GroupStudentGradeSerializer(serializers.ModelSerializer):
    """Read-only serializer for a student's exam record inside a group."""
    assignment_id = serializers.IntegerField(source='id_assignment', read_only=True)
    student_id = serializers.IntegerField(source='student.pk', read_only=True)
    matricula = serializers.CharField(source='student.matricula', read_only=True)
    full_name = serializers.CharField(source='student.full_name', read_only=True)
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = ExamAssignment
        fields = [
            'assignment_id', 'student_id', 'matricula', 'full_name',
            'status', 'status_label', 'score', 'is_passed',
            'attempt_date', 'available_from', 'available_to',
        ]
        read_only_fields = fields

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


# ---------------------------------------------------------------------------
# Output serializer (read operations)
# ---------------------------------------------------------------------------

class ExamSerializer(serializers.ModelSerializer):
    """Read-only serializer for listing/detail responses."""
    subject_name = serializers.CharField(source='id_subject.name', read_only=True)
    subject_level = serializers.IntegerField(source='id_subject.level_number', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    unit_name = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id_exam', 'name', 'title',
            'id_subject', 'subject_name', 'subject_level',
            'id_teacher', 'teacher_name',
            'unit_number', 'unit_name',
            'difficulty_level', 'difficulty_label',
            'secure_mode', 'minimum_score', 'creation_date', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_teacher_name(self, obj):
        return f"{obj.id_teacher.first_name} {obj.id_teacher.last_name}"

    def get_unit_name(self, obj):
        unit = Unit.objects.filter(
            id_subject=obj.id_subject, unit_number=obj.unit_number
        ).first()
        return unit.unit_name if unit else None


# ---------------------------------------------------------------------------
# Created-by-me serializer (no teacher fields — they are the requester)
# ---------------------------------------------------------------------------

class CreatedByMeExamSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for GET /exams/created-by-me.
    Omits teacher fields (caller is always the creator).
    Resolves unit_name from prefetched units to avoid N+1.
    """
    subject_name = serializers.CharField(source='id_subject.name', read_only=True)
    subject_level = serializers.IntegerField(source='id_subject.level_number', read_only=True)
    difficulty_label = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    unit_name = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id_exam', 'name', 'title',
            'id_subject', 'subject_name', 'subject_level',
            'unit_number', 'unit_name',
            'difficulty_level', 'difficulty_label',
            'secure_mode', 'minimum_score', 'creation_date', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_unit_name(self, obj):
        # Resolve from prefetched units — avoids one DB query per exam
        for unit in obj.id_subject.units.all():
            if unit.unit_number == obj.unit_number:
                return unit.unit_name
        return None


# ---------------------------------------------------------------------------
# Create serializer
# ---------------------------------------------------------------------------

class ExamCreateSerializer(serializers.Serializer):
    """Input serializer for POST /exams/."""
    name = serializers.CharField(max_length=200, required=True)
    id_subject = serializers.IntegerField(required=True)
    unit_number = serializers.IntegerField(min_value=1, required=True)
    difficulty_level = serializers.ChoiceField(
        choices=Exam.DIFFICULTY_CHOICES, required=True
    )
    secure_mode = serializers.BooleanField(default=False, required=False)
    minimum_score = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=8.00, required=False,
        min_value=0, max_value=10,
    )

    def validate_name(self, value):
        return value.strip()

    def validate_id_subject(self, value):
        try:
            subject = Subject.objects.prefetch_related('units').get(pk=value)
        except Subject.DoesNotExist:
            raise serializers.ValidationError('La materia especificada no existe.')
        if not subject.status:
            raise serializers.ValidationError('La materia especificada está inactiva.')
        self.context['_subject'] = subject
        return value

    def validate(self, attrs):
        subject = self.context.get('_subject')
        if not subject:
            return attrs

        unit_number = attrs.get('unit_number')
        max_units = subject.units.count()

        if max_units > 0 and unit_number > max_units:
            raise serializers.ValidationError({
                'unit_number': (
                    f'La unidad {unit_number} excede el número de unidades '
                    f'de la materia "{subject.name}" ({max_units}).'
                )
            })

        if max_units > 0:
            unit_exists = subject.units.filter(unit_number=unit_number).exists()
            if not unit_exists:
                raise serializers.ValidationError({
                    'unit_number': (
                        f'No existe la unidad {unit_number} registrada en la materia "{subject.name}".'
                    )
                })

        return attrs


# ---------------------------------------------------------------------------
# Update serializer
# ---------------------------------------------------------------------------

class ExamUpdateSerializer(serializers.Serializer):
    """Input serializer for PUT /exams/{id}/."""
    name = serializers.CharField(max_length=200, required=True)
    id_subject = serializers.IntegerField(required=True)
    unit_number = serializers.IntegerField(min_value=1, required=True)
    difficulty_level = serializers.ChoiceField(
        choices=Exam.DIFFICULTY_CHOICES, required=True
    )
    secure_mode = serializers.BooleanField(required=True)
    minimum_score = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=True,
        min_value=0, max_value=10,
    )
    status = serializers.BooleanField(required=True)

    def validate_name(self, value):
        return value.strip()

    def validate_id_subject(self, value):
        try:
            subject = Subject.objects.prefetch_related('units').get(pk=value)
        except Subject.DoesNotExist:
            raise serializers.ValidationError('La materia especificada no existe.')
        if not subject.status:
            raise serializers.ValidationError('La materia especificada está inactiva.')
        self.context['_subject'] = subject
        return value

    def validate(self, attrs):
        subject = self.context.get('_subject')
        if not subject:
            return attrs

        unit_number = attrs.get('unit_number')
        max_units = subject.units.count()

        if max_units > 0 and unit_number > max_units:
            raise serializers.ValidationError({
                'unit_number': (
                    f'La unidad {unit_number} excede el número de unidades '
                    f'de la materia "{subject.name}" ({max_units}).'
                )
            })

        if max_units > 0:
            unit_exists = subject.units.filter(unit_number=unit_number).exists()
            if not unit_exists:
                raise serializers.ValidationError({
                    'unit_number': (
                        f'No existe la unidad {unit_number} registrada en la materia "{subject.name}".'
                    )
                })

        return attrs


# ---------------------------------------------------------------------------
# Status-only serializer
# ---------------------------------------------------------------------------

class ExamStatusSerializer(serializers.Serializer):
    """Input serializer for PATCH /exams/{id}/status/."""
    status = serializers.BooleanField(required=True)


# ---------------------------------------------------------------------------
# Secure mode serializer
# ---------------------------------------------------------------------------

class ExamSecureModeSerializer(serializers.Serializer):
    """Input serializer for PATCH /exams/{id}/secure-mode/."""
    secure_mode = serializers.BooleanField(required=True)


# ---------------------------------------------------------------------------
# Exam Assignment serializers
# ---------------------------------------------------------------------------

class ExamAssignSerializer(serializers.Serializer):
    """
    Input serializer for POST /exam-assignments/assign.
    Validates bulk group-sync for an exam assignment.
    group_ids may be empty (removes all pending assignments).
    """
    exam_id = serializers.IntegerField(required=True)
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=True,   # empty list = remove all pending assignments
    )
    available_from = serializers.DateTimeField(required=True)
    available_to = serializers.DateTimeField(required=True)

    def validate_exam_id(self, value):
        try:
            exam = Exam.objects.get(pk=value)
        except Exam.DoesNotExist:
            raise serializers.ValidationError('El examen especificado no existe.')
        if not exam.status:
            raise serializers.ValidationError('El examen especificado está inactivo.')
        self.context['_exam'] = exam
        return value

    def validate_group_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Se enviaron IDs de grupo duplicados.')

        if not value:
            self.context['_groups'] = []
            return value

        groups = Group.objects.filter(pk__in=value)
        found_ids = set(groups.values_list('pk', flat=True))
        missing = set(value) - found_ids
        if missing:
            raise serializers.ValidationError(
                f'Los siguientes grupos no existen: {sorted(missing)}'
            )

        self.context['_groups'] = list(groups)
        return value

    def validate(self, attrs):
        if attrs['available_from'] >= attrs['available_to']:
            raise serializers.ValidationError({
                'available_to': 'La fecha de cierre debe ser posterior a la de apertura.',
            })
        return attrs


class ExamAssignmentGroupSummarySerializer(serializers.Serializer):
    """Read-only serializer showing which groups an exam is currently assigned to."""
    group_id = serializers.IntegerField()
    group_label = serializers.CharField()
    students_assigned = serializers.IntegerField()
    available_from = serializers.DateTimeField()
    available_to = serializers.DateTimeField()


class ExamGroupStatsSerializer(serializers.Serializer):
    """Read-only serializer for per-group exam stats dashboard."""
    group_id = serializers.IntegerField()
    group_label = serializers.CharField()
    total_students = serializers.IntegerField()
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    highest_score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    lowest_score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    approval_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    pending_count = serializers.IntegerField()
    in_progress_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()


class ExamAssignmentOutputSerializer(serializers.ModelSerializer):
    """Read-only serializer for exam assignment records."""
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    student_name = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamAssignment
        fields = [
            'id_assignment', 'exam_id', 'exam_name',
            'student_id', 'student_name',
            'group_id', 'group_name',
            'status', 'score', 'is_passed',
            'assigned_at', 'available_from', 'available_to',
            'attempt_date', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_group_name(self, obj):
        return str(obj.group)


# ---------------------------------------------------------------------------
# Student "My Assignments" serializer
# ---------------------------------------------------------------------------

class MyAssignmentSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the student's assignment list.
    Includes exam context, subject info, computed availability flags.
    """
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    subject_name = serializers.CharField(source='exam.id_subject.name', read_only=True)
    unit_number = serializers.IntegerField(source='exam.unit_number', read_only=True)
    difficulty_level = serializers.CharField(source='exam.difficulty_level', read_only=True)
    difficulty_label = serializers.CharField(
        source='exam.get_difficulty_level_display', read_only=True,
    )
    secure_mode = serializers.BooleanField(source='exam.secure_mode', read_only=True)
    group_label = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()

    class Meta:
        model = ExamAssignment
        fields = [
            'id_assignment',
            'exam_id', 'exam_name', 'exam_title',
            'subject_name', 'unit_number',
            'difficulty_level', 'difficulty_label',
            'secure_mode',
            'group_id', 'group_label',
            'status', 'score', 'is_passed',
            'assigned_at', 'available_from', 'available_to',
            'attempt_date',
            'is_available', 'is_expired', 'can_start',
        ]
        read_only_fields = fields

    def get_group_label(self, obj):
        return str(obj.group)

    def get_is_available(self, obj):
        now = timezone.now()
        return obj.available_from <= now <= obj.available_to

    def get_is_expired(self, obj):
        return timezone.now() > obj.available_to

    def get_can_start(self, obj):
        now = timezone.now()
        within_window = obj.available_from <= now <= obj.available_to
        return within_window and obj.status in ('pending', 'in_progress')


# ---------------------------------------------------------------------------
# Query-param input serializer for my-assignments (Rule 1: validate all inputs)
# ---------------------------------------------------------------------------

class MyAssignmentQuerySerializer(serializers.Serializer):
    """Validates the query parameters accepted by MyAssignmentsView."""
    VALID_STATUSES = ('pending', 'in_progress', 'completed')

    status = serializers.ChoiceField(
        choices=VALID_STATUSES,
        required=False,
        allow_null=True,
        default=None,
    )
    include_completed = serializers.BooleanField(required=False, default=False)


# ---------------------------------------------------------------------------
# Query-param input serializer for created-by-me
# ---------------------------------------------------------------------------

class CreatedByMeQuerySerializer(serializers.Serializer):
    """Validates the query parameters accepted by CreatedByMeExamsView."""
    status = serializers.BooleanField(required=False, allow_null=True, default=None)
    id_subject = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)
    difficulty_level = serializers.ChoiceField(
        choices=Exam.DIFFICULTY_CHOICES,
        required=False,
        allow_null=True,
        default=None,
    )
    search = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
        default=None, max_length=100,
    )

    def validate_search(self, value):
        if value:
            return value.strip() or None
        return None
