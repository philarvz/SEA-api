"""
Helpers for bulk question import from .xlsx (multiple header conventions).
Supports English headers (question_text, subject_id, options, …) and Spanish
layouts (enunciado, materia, opcion_1..4, dificultad MEDIA/ALTA, bloom RECORDAR, …).
"""

from __future__ import annotations

import unicodedata
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser

from apps.academic.models import Subject
from apps.users.models import TeacherProfile

from .models import Question

_VALID_BLOOM = frozenset({
    'remember',
    'understand',
    'apply',
    'analyze',
    'evaluate',
    'create',
})


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s).strip().lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


# Canonical internal names -> accepted column headers (lowercase, no accents required in file)
CANONICAL_HEADERS: dict[str, tuple[str, ...]] = {
    'question_text': (
        'question_text',
        'enunciado',
        'pregunta',
        'texto',
        'texto_pregunta',
    ),
    'type': ('type', 'tipo'),
    'subject_id': ('subject_id', 'id_materia', 'id_subject', 'materia_id'),
    'subject_name': ('materia', 'subject_name', 'nombre_materia', 'materia_nombre'),
    'options': ('options', 'opciones'),
    'correct_answers': (
        'correct_answers',
        'correctas',
        'respuesta_correcta',
        'respuestas_correctas',
    ),
    'difficulty': ('difficulty', 'dificultad'),
    'bloom_level': ('bloom_level', 'bloom', 'nivel_bloom', 'taxonomia', 'taxonomía'),
    'image_url': ('image_url', 'imagen_url', 'url_imagen', 'url_imagen_opcional'),
    'test_code': ('test_code', 'codigo_prueba', 'código_prueba', 'codigo_test', 'pruebas'),
    'points': ('points', 'puntos', 'puntaje'),
}

_DIFFICULTY_ALIASES: dict[str, str] = {
    'easy': 'easy',
    'e': 'easy',
    'baja': 'easy',
    'facil': 'easy',
    'fácil': 'easy',
    'low': 'easy',
    'medium': 'medium',
    'm': 'medium',
    'medio': 'medium',
    'media': 'medium',
    'normal': 'medium',
    'hard': 'hard',
    'h': 'hard',
    'alta': 'hard',
    'dificil': 'hard',
    'difícil': 'hard',
    'high': 'hard',
}

_BLOOM_ALIASES: dict[str, str] = {
    'remember': 'remember',
    'recordar': 'remember',
    'understand': 'understand',
    'comprender': 'understand',
    'comprension': 'understand',
    'comprensión': 'understand',
    'apply': 'apply',
    'aplicar': 'apply',
    'analyze': 'analyze',
    'analizar': 'analyze',
    'analisis': 'analyze',
    'análisis': 'analyze',
    'evaluate': 'evaluate',
    'evaluar': 'evaluate',
    'create': 'create',
    'crear': 'create',
}


def normalize_header_row(row: tuple[Any, ...] | list[Any]) -> list[str]:
    out: list[str] = []
    for h in row:
        if h is None:
            out.append('')
        else:
            out.append(_strip_accents(str(h)))
    return out


def build_column_maps(headers_normalized: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """
    Returns:
      - col_by_canon: canonical field -> column index
      - col_by_header: every header -> index (for opcion_1 etc.)
    """
    col_by_header: dict[str, int] = {}
    for i, h in enumerate(headers_normalized):
        if h and h not in col_by_header:
            col_by_header[h] = i

    col_by_canon: dict[str, int] = {}
    for canon, aliases in CANONICAL_HEADERS.items():
        for alias in aliases:
            key = _strip_accents(alias)
            if key in col_by_header:
                col_by_canon[canon] = col_by_header[key]
                break

    return col_by_canon, col_by_header


def validate_required_columns(col_by_canon: dict[str, int]) -> str | None:
    if 'question_text' not in col_by_canon:
        return 'Falta una columna de enunciado (question_text / enunciado / pregunta).'
    if 'type' not in col_by_canon:
        return 'Falta la columna de tipo (type / tipo).'
    if 'subject_id' not in col_by_canon and 'subject_name' not in col_by_canon:
        return 'Falta materia: use subject_id / id_materia o materia (nombre exacto).'
    return None


def worksheet_for_question_import(workbook) -> Any:
    """Prioriza Plantilla (ES); admite Plantilla_ES por compatibilidad con archivos antiguos."""
    titles = getattr(workbook, 'sheetnames', None) or []
    for name in ('Plantilla', 'Plantilla_ES'):
        if name in titles:
            return workbook[name]
    return workbook.active


def get_cell(row: tuple[Any, ...] | list[Any], idx: int | None, default=None):
    if idx is None or idx < 0 or idx >= len(row):
        return default
    v = row[idx]
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip()
    return v


def parse_difficulty(raw: Any) -> str:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 'medium'
    s = _strip_accents(str(raw))
    s_compact = s.replace(' ', '')
    mapped = _DIFFICULTY_ALIASES.get(s) or _DIFFICULTY_ALIASES.get(s_compact)
    if mapped:
        return mapped
    return 'medium'


def parse_bloom(raw: Any) -> str:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return 'remember'
    s = _strip_accents(str(raw))
    s_compact = s.replace(' ', '').replace('_', '')
    if s in _VALID_BLOOM:
        return s
    mapped = _BLOOM_ALIASES.get(s) or _BLOOM_ALIASES.get(s_compact)
    if mapped and mapped in _VALID_BLOOM:
        return mapped
    return 'remember'


def parse_question_type(raw: Any) -> str:
    """Etiquetas en español de la plantilla y códigos en inglés (MULTIPLE_CHOICE, …)."""
    if raw is None:
        return 'MULTIPLE_CHOICE'
    s0 = str(raw).strip()
    if not s0:
        return 'MULTIPLE_CHOICE'

    sk = _strip_accents(s0).lower()
    sk = ' '.join(sk.split())
    es_to_canon = {
        'seleccion unica': 'MULTIPLE_CHOICE',
        'seleccion multiple': 'MULTIPLE_SELECTION',
        'respuesta abierta': 'OPEN',
        'codigo': 'CODE',
    }
    if sk in es_to_canon:
        return es_to_canon[sk]
    sk_compact = sk.replace(' ', '')
    compact_map = {
        'seleccionunica': 'MULTIPLE_CHOICE',
        'seleccionmultiple': 'MULTIPLE_SELECTION',
        'respuestaabierta': 'OPEN',
        'codigo': 'CODE',
    }
    if sk_compact in compact_map:
        return compact_map[sk_compact]

    su = s0.upper().replace('-', '_').replace(' ', '_')
    aliases = {'MC': 'MULTIPLE_CHOICE', 'MS': 'MULTIPLE_SELECTION'}
    if su in aliases:
        return aliases[su]
    codes = {c[0] for c in Question.QUESTION_TYPE_CHOICES}
    if su in codes:
        return su
    return 'MULTIPLE_CHOICE'


def collect_options_from_row(
    row: tuple[Any, ...] | list[Any],
    col_by_header: dict[str, int],
) -> list[str]:
    """opcion_1..4 / opción_1 / option_1 …"""
    opts: list[str] = []
    for i in range(1, 5):
        idx = None
        for key in (
            f'opcion_{i}',
            f'opción_{i}',
            f'option_{i}',
            f'op{i}',
        ):
            k = _strip_accents(key)
            if k in col_by_header:
                idx = col_by_header[k]
                break
        if idx is not None:
            v = get_cell(row, idx)
            if v is not None and str(v).strip():
                opts.append(str(v).strip())
    return opts


def _allowed_subject_ids_for_user(user: AbstractBaseUser | None) -> frozenset[int] | None:
    """
    None = sin restricción (admin u otro rol).
    frozenset vacío = docente sin materias asignadas.
    frozenset con ids = solo esas materias.
    """
    if user is None:
        return None
    role = getattr(user, 'role', None)
    if role != 'teacher':
        return None
    try:
        profile = TeacherProfile.objects.get(user_id=user.pk)
    except TeacherProfile.DoesNotExist:
        return frozenset()
    return frozenset(profile.subjects.values_list('id_subject', flat=True))


def resolve_subject_id(
    row: tuple[Any, ...] | list[Any],
    col_by_canon: dict[str, int],
    user: AbstractBaseUser | None = None,
) -> int:
    allowed = _allowed_subject_ids_for_user(user)

    if 'subject_id' in col_by_canon:
        raw = get_cell(row, col_by_canon['subject_id'])
        sid = int(raw)
        sub = Subject.objects.filter(pk=sid, status=True).first()
        if not sub:
            raise ValueError('El id_subject no existe o la materia está inactiva.')
        if allowed is not None and sub.pk not in allowed:
            raise ValueError(
                'No tiene permiso para esa materia. Elija una materia de la hoja Materias de su plantilla.'
            )
        return sid

    name = get_cell(row, col_by_canon['subject_name'])
    if not name:
        raise ValueError('La celda de materia (nombre) está vacía.')
    name = str(name).strip()
    qs = Subject.objects.filter(name__iexact=name, status=True)
    if allowed is not None:
        qs = qs.filter(pk__in=allowed)
    sub = qs.first()
    if not sub:
        if allowed is not None and Subject.objects.filter(name__iexact=name, status=True).exists():
            raise ValueError(
                f'La materia "{name}" existe pero no está asignada a su perfil de docente.'
            )
        raise ValueError(
            f'No existe una materia activa "{name}". Elija exactamente un nombre de la hoja Materias.'
        )
    return sub.pk


def parse_points(raw: Any) -> int:
    if raw is None or raw == '':
        return 1
    try:
        p = int(float(raw))
        return max(1, p)
    except (TypeError, ValueError):
        return 1
