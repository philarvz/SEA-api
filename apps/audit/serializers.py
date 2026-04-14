"""Serializers for the Audit module."""

from functools import lru_cache

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.academic.models import Generation, Group, Period

from .models import AuditLog

User = get_user_model()

SENSITIVE_FIELDS = {'password', 'token', 'secret_key'}

# Campos que sí son útiles para la vista de administración.
RELEVANT_FIELDS = {
    'username',
    'first_name',
    'last_name',
    'email',
    'role',
    'status',
    'is_active',
    'group_letter',
    'group_id',
    'generation',
    'id_generation',
    'academic_level',
    'period_name',
    'id_period',
    'unit_number',
    'title',
    'name',
    'user_id',
}

FIELD_LABELS = {
    'username': 'Usuario',
    'first_name': 'Nombre',
    'last_name': 'Apellidos',
    'email': 'Correo',
    'role': 'Rol',
    'status': 'Estado',
    'is_active': 'Activo',
    'group_letter': 'Grupo',
    'group_id': 'Grupo',
    'generation': 'Generación',
    'id_generation': 'Generación',
    'academic_level': 'Nivel académico',
    'period_name': 'Periodo',
    'id_period': 'Periodo',
    'unit_number': 'Unidad',
    'title': 'Título',
    'name': 'Nombre',
    'user_id': 'Usuario',
}

# Agrupa aliases que representan el mismo dato funcional.
CANONICAL_FIELD_KEY = {
    'status': 'status',
    'is_active': 'status',
    'period_name': 'period',
    'id_period': 'period',
    'group_letter': 'group',
    'group_id': 'group',
    'generation': 'generation',
    'id_generation': 'generation',
    'username': 'user',
    'user_id': 'user',
}

# En caso de duplicidad, prioriza el campo más legible para el admin.
FIELD_PRIORITY = {
    'status': 30,
    'is_active': 20,
    'period_name': 30,
    'id_period': 20,
    'group_letter': 30,
    'group_id': 20,
    'generation': 30,
    'id_generation': 20,
    'username': 30,
    'user_id': 20,
}


def translate_table_name(table_name):
    """Convierte nombres de tabla técnicos a etiquetas legibles para admin."""
    table_map = {
        'user': 'Usuarios',
        'student_profile': 'Perfiles de estudiante',
        'teacher_profile': 'Perfiles de docente',
        'generation': 'Generaciones',
        'group': 'Grupos',
        'period': 'Periodos',
        'subject': 'Materias',
        'unit': 'Unidades',
        'exam': 'Exámenes',
        'question': 'Preguntas',
    }
    return table_map.get(table_name, 'Registro')


def translate_operation(operation_type):
    """Traduce la operación técnica a una etiqueta legible."""
    operation_map = {
        'INSERT': 'Creación',
        'UPDATE': 'Actualización',
        'DELETE': 'Eliminación',
    }
    return operation_map.get((operation_type or '').upper(), operation_type)


def get_username(user_id):
    if user_id in (None, '', 'null'):
        return None
    return _get_username_cached(str(user_id))


@lru_cache(maxsize=2048)
def _get_username_cached(user_id):
    if user_id in (None, '', 'null'):
        return None
    try:
        user = User.objects.get(pk=user_id)
        return user.username
    except (User.DoesNotExist, ValueError, TypeError):
        return user_id


def get_group_letter(group_id):
    if group_id in (None, '', 'null'):
        return None
    return _get_group_letter_cached(str(group_id))


@lru_cache(maxsize=2048)
def _get_group_letter_cached(group_id):
    if group_id in (None, '', 'null'):
        return None
    try:
        group = Group.objects.select_related('id_generation').get(pk=group_id)
        return group.group_letter
    except (Group.DoesNotExist, ValueError, TypeError):
        return group_id


def get_period_name(period_id):
    if period_id in (None, '', 'null'):
        return None
    return _get_period_name_cached(str(period_id))


@lru_cache(maxsize=2048)
def _get_period_name_cached(period_id):
    if period_id in (None, '', 'null'):
        return None
    try:
        period = Period.objects.get(pk=period_id)
        return period.period_name
    except (Period.DoesNotExist, ValueError, TypeError):
        return period_id


def get_generation_label(generation_id):
    if generation_id in (None, '', 'null'):
        return None
    return _get_generation_label_cached(str(generation_id))


@lru_cache(maxsize=2048)
def _get_generation_label_cached(generation_id):
    if generation_id in (None, '', 'null'):
        return None
    try:
        generation = Generation.objects.get(pk=generation_id)
        return generation.year
    except (Generation.DoesNotExist, ValueError, TypeError):
        return generation_id


def get_app_user_name(app_user):
    if app_user and app_user not in ('anonymous', ''):
        return _get_app_user_name_cached(str(app_user))
    return 'Usuario desconocido'


@lru_cache(maxsize=2048)
def _get_app_user_name_cached(app_user):
    try:
        user = User.objects.get(pk=app_user)
        return user.get_full_name() or user.username
    except (User.DoesNotExist, ValueError, TypeError):
        return app_user


def _normalize_value(value):
    if value is None:
        return '-'
    return value


def _as_mapping(value):
    """Ensure old/new values are dict-like before reading keys."""
    if isinstance(value, dict):
        return value
    return {}


def _transform_field_values(field, old_value, new_value):
    if field == 'user_id':
        return get_username(old_value), get_username(new_value), 'user_id'
    if field == 'group_id':
        return get_group_letter(old_value), get_group_letter(new_value), 'group_id'
    if field == 'id_period':
        return get_period_name(old_value), get_period_name(new_value), 'id_period'
    if field == 'id_generation':
        return get_generation_label(old_value), get_generation_label(new_value), 'id_generation'
    return old_value, new_value, field


def _handle_sensitive_field(field, old_value, new_value):
    """Handle sensitive field by masking values."""
    return {
        'field': FIELD_LABELS.get(field, field),
        'old': 'CAMBIADO' if old_value not in (None, '') else '-',
        'new': 'CAMBIADO' if new_value not in (None, '') else '-',
    }


def _process_field_change(field, old_value, new_value, dedup_changes):
    """
    Process a field change and update dedup_changes dict if it should be included.
    Returns True if the field was processed, False otherwise.
    """
    old_value, new_value, field = _transform_field_values(field, old_value, new_value)

    # Omitir si después de transformar quedan iguales
    if old_value == new_value:
        return False

    canonical_key = CANONICAL_FIELD_KEY.get(field, field)
    current_priority = FIELD_PRIORITY.get(field, 0)

    change_payload = {
        'field': FIELD_LABELS.get(field, field),
        'old': _normalize_value(old_value),
        'new': _normalize_value(new_value),
        '_priority': current_priority,
    }

    existing = dedup_changes.get(canonical_key)
    if not existing or current_priority >= existing.get('_priority', -1):
        dedup_changes[canonical_key] = change_payload

    return True


def filter_audit_log_for_admin(audit_log):
    """
    Recibe un registro de auditoría completo y devuelve solo la información
    relevante para la vista de administrador, ocultando datos sensibles y
    transformando IDs internos a valores legibles.
    """
    filtered_log = {
        'table': translate_table_name(audit_log.get('table_name')),
        'operation': translate_operation(audit_log.get('operation_type')),
        'changed_at': audit_log.get('changed_at'),
        'user': audit_log.get('app_user_name') or audit_log.get('app_user') or 'Desconocido',
        'changes': [],
    }

    old_values = _as_mapping(audit_log.get('old_values'))
    new_values = _as_mapping(audit_log.get('new_values'))
    all_fields = set(old_values.keys()) | set(new_values.keys())

    dedup_changes = {}

    for field in all_fields:
        old_value = old_values.get(field)
        new_value = new_values.get(field)

        # Omitir campos idénticos
        if old_value == new_value:
            continue

        normalized_field = str(field or '').lower()

        # Campos sensibles
        if normalized_field in SENSITIVE_FIELDS:
            filtered_log['changes'].append(_handle_sensitive_field(field, old_value, new_value))
            continue

        # Agregar solo campos relevantes
        if field not in RELEVANT_FIELDS:
            continue

        _process_field_change(field, old_value, new_value, dedup_changes)

    filtered_log['changes'].extend([
        {
            'field': change['field'],
            'old': change['old'],
            'new': change['new'],
        }
        for change in dedup_changes.values()
    ])

    return filtered_log


def has_visible_admin_changes(instance):
    """Return True when the audit row has at least one meaningful admin change."""
    payload = {
        'table_name': instance.table_name,
        'operation_type': instance.operation_type,
        'old_values': instance.old_values,
        'new_values': instance.new_values,
        'changed_at': instance.changed_at,
        'app_user': instance.app_user,
        'app_user_name': get_app_user_name(instance.app_user),
    }
    filtered = filter_audit_log_for_admin(payload)
    return bool(filtered.get('changes'))


class AuditLogSerializer(serializers.ModelSerializer):
    app_user_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'table_name',
            'operation_type',
            'old_values',
            'new_values',
            'changed_at',
            'app_user',
            'app_user_name',
            'client_addr',
        ]
        read_only_fields = fields

    def get_app_user_name(self, obj):
        return get_app_user_name(obj.app_user)


class AuditLogAdminSerializer(serializers.Serializer):
    """Salida simplificada y segura para la vista de bitácora de administrador."""

    def to_representation(self, instance):
        payload = {
            'table_name': instance.table_name,
            'operation_type': instance.operation_type,
            'old_values': instance.old_values,
            'new_values': instance.new_values,
            'changed_at': instance.changed_at,
            'app_user': instance.app_user,
            'app_user_name': get_app_user_name(instance.app_user),
        }
        return filter_audit_log_for_admin(payload)
