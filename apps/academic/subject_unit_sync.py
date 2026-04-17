"""
Synchronize Subject.units from a validated PUT payload.
"""

from .models import Subject, Unit


class SubjectUnitSyncError(Exception):
    """Raised when unit sync cannot complete (business rules)."""

    def __init__(self, detail):
        super().__init__(str(detail))
        self.detail = detail


def _temp_unit_number(unit_pk: int) -> int:
    """Avoid unique collisions while reordering (DB has no unique constraint, but keep values sane)."""
    return 10_000 + unit_pk


def sync_subject_units(subject: Subject, validated_items: list[dict]) -> None:
    """
    Replace units with validated_items (full desired state). Max 9 units.

    Rules:
    - Cannot delete or change unit_number of a unit if an Exam references that unit_number
      for this subject (exams store unit_number, not Unit FK).
    - unit_name can always be updated.
    """
    from apps.exams.models import Exam

    if not validated_items:
        for unit in list(Unit.objects.filter(id_subject=subject)):
            if Exam.objects.filter(id_subject=subject, unit_number=unit.unit_number).exists():
                raise SubjectUnitSyncError(
                    {
                        'units': (
                            f'No se puede eliminar la unidad {unit.unit_number} porque hay '
                            'exámenes asociados a ese número de unidad.'
                        )
                    }
                )
            unit.delete()
        return

    existing_by_id = {u.pk: u for u in Unit.objects.filter(id_subject=subject)}
    payload_ids = {item['id_unit'] for item in validated_items if item.get('id_unit') is not None}

    for uid, unit in list(existing_by_id.items()):
        if uid not in payload_ids:
            if Exam.objects.filter(id_subject=subject, unit_number=unit.unit_number).exists():
                raise SubjectUnitSyncError(
                    {
                        'units': (
                            f'No se puede eliminar la unidad {unit.unit_number} porque hay '
                            'exámenes asociados a ese número de unidad.'
                        )
                    }
                )
            unit.delete()

    existing_by_id = {u.pk: u for u in Unit.objects.filter(id_subject=subject)}

    for item in validated_items:
        id_unit = item.get('id_unit')
        if id_unit is None:
            continue
        try:
            unit = existing_by_id[id_unit]
        except KeyError as exc:
            raise SubjectUnitSyncError({'units': 'Se referenció una unidad que no pertenece a esta materia.'}) from exc

        new_num = item['unit_number']
        if unit.unit_number != new_num:
            if Exam.objects.filter(id_subject=subject, unit_number=unit.unit_number).exists():
                raise SubjectUnitSyncError(
                    {
                        'units': (
                            f'No se puede cambiar el número de la unidad {unit.unit_number} '
                            'porque hay exámenes asociados a ese número.'
                        )
                    }
                )

    for unit in Unit.objects.filter(id_subject=subject):
        unit.unit_number = _temp_unit_number(unit.pk)
        unit.save(update_fields=['unit_number'])

    with_id = [i for i in validated_items if i.get('id_unit') is not None]
    without_id = [i for i in validated_items if i.get('id_unit') is None]

    for item in sorted(with_id, key=lambda x: x['unit_number']):
        unit = Unit.objects.select_for_update().get(pk=item['id_unit'], id_subject=subject)
        unit.unit_name = item['unit_name']
        unit.unit_number = item['unit_number']
        unit.save(update_fields=['unit_name', 'unit_number'])

    for item in sorted(without_id, key=lambda x: x['unit_number']):
        Unit.objects.create(
            id_subject=subject,
            unit_name=item['unit_name'],
            unit_number=item['unit_number'],
        )
