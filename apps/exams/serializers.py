"""
Serializers for the Exams module.
Covers: Exam CRUD operations with academic validation.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import Exam
from apps.academic.models import Subject, Unit


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
            'secure_mode', 'creation_date', 'status',
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
