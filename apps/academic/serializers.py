"""
Serializers for the Academic module.
Covers: Generation, Period, Group, Subject and auxiliary operations.
"""

from rest_framework import serializers

from .models import Generation, Period, Group, Subject, Unit
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
    class Meta:
        model = Period
        fields = ['id_period', 'year', 'period_name', 'start_date', 'end_date', 'status']
        read_only_fields = ['id_period']

    def validate_year(self, value):
        if value < 1900 or value > 2200:
            raise serializers.ValidationError('El año del periodo no es válido.')
        return value

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and start >= end:
            raise serializers.ValidationError(
                {'end_date': 'La fecha de fin debe ser posterior a la fecha de inicio.'}
            )
        return attrs


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------

class GroupCreateSerializer(serializers.Serializer):
    """Input serializer for POST /groups/ — id_period is resolved automatically."""
    id_generation = serializers.IntegerField(required=True)
    group_letter = serializers.CharField(max_length=5, required=True)
    academic_level = serializers.IntegerField(min_value=1, required=True)
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
        if generation and academic_level > generation.total_levels:
            raise serializers.ValidationError({
                'academic_level': f'El nivel académico no puede exceder {generation.total_levels} (total de niveles de la generación).'
            })
        return attrs


class GroupUpdateSerializer(serializers.Serializer):
    """Input serializer for PUT /groups/{id}/ — generation is immutable."""
    group_letter = serializers.CharField(max_length=5, required=True)
    academic_level = serializers.IntegerField(min_value=1, required=True)
    status = serializers.BooleanField(required=True)

    def validate_group_letter(self, value):
        return value.strip().upper()


class GroupSerializer(serializers.ModelSerializer):
    """Output serializer for read operations."""
    generation_year = serializers.IntegerField(source='id_generation.year', read_only=True)
    generation_total_levels = serializers.IntegerField(source='id_generation.total_levels', read_only=True)
    period_info = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id_group', 'id_generation', 'generation_year',
            'generation_total_levels',
            'id_period', 'period_info',
            'group_letter', 'academic_level', 'status',
        ]

    def get_period_info(self, obj):
        if obj.id_period:
            return f"{obj.id_period.year} - {obj.id_period.period_name}"
        return None


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


# ---------------------------------------------------------------------------
# Shared / auxiliary
# ---------------------------------------------------------------------------

class StatusUpdateSerializer(serializers.Serializer):
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
