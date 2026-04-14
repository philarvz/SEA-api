from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from apps.academic.models import Subject

from .subject_access import allowed_subject_ids_for_question_user

FIRST_DATA_ROW = 2
LAST_DATA_ROW = 5001

TYPE_OPTIONS_ES = [
    'Selección única',
    'Selección múltiple',
    'Respuesta abierta',
    'Código',
]
DIFF_OPTIONS_ES = ['BAJA', 'MEDIA', 'ALTA']
BLOOM_OPTIONS_ES = [
    'RECORDAR',
    'COMPRENDER',
    'APLICAR',
    'ANALIZAR',
    'EVALUAR',
    'CREAR',
]

def subjects_for_template_user(user) -> list[Subject]:
    allowed = allowed_subject_ids_for_question_user(user)
    qs = Subject.objects.filter(status=True).order_by('level_number', 'name')
    if allowed is not None:
        qs = qs.filter(pk__in=allowed)
    return list(qs)

def _inline_list_formula(values: list[str]) -> str:
    return '"' + ','.join(values) + '"'

def _add_list_validation(ws, col_letter: str, formula1: str) -> None:
    dv = DataValidation(type='list', formula1=formula1, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f'{col_letter}{FIRST_DATA_ROW}:{col_letter}{LAST_DATA_ROW}')

def _example_data_rows(subjects: list[Subject]) -> list[list]:
    sub = subjects[0].name if subjects else ''
    return [
        [
            sub,
            'Selección única',
            '¿Cuál es la capital de Francia?',
            'MEDIA',
            'RECORDAR',
            1,
            '',
            'París',
            'Londres',
            'Madrid',
            'Roma',
            '1',
            '',
        ],
        [
            sub,
            'Selección múltiple',
            '¿Cuáles de los siguientes son números primos?',
            'MEDIA',
            'APLICAR',
            1,
            '',
            '2',
            '4',
            '3',
            '9',
            '1,3',
            '',
        ],
        [
            sub,
            'Respuesta abierta',
            'Explique brevemente qué es una variable en programación.',
            'ALTA',
            'CREAR',
            2,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
        ],
        [
            sub,
            'Código',
            'Escriba una función suma(a, b) que devuelva la suma de a y b.',
            'MEDIA',
            'APLICAR',
            1,
            '',
            '',
            '',
            '',
            '',
            '',
            'assert suma(2, 3) == 5',
        ],
    ]


def build_questions_template_workbook(user) -> bytes:
    subjects = subjects_for_template_user(user)
    wb = Workbook()

    ws_m = wb.active
    ws_m.title = 'Materias'
    ws_m.cell(1, 1, 'materia')
    for i, sub in enumerate(subjects, start=2):
        ws_m.cell(row=i, column=1, value=sub.name)
    ws_m.column_dimensions['A'].width = 52

    last_sub_row = max(2, 1 + len(subjects))
    sub_name_range = f"='Materias'!$A$2:$A${last_sub_row}"

    bold_center = Font(bold=True)
    center = Alignment(horizontal='center')
    wrap = Alignment(wrap_text=True)

    ws = wb.create_sheet('Plantilla')
    headers = [
        'materia',
        'tipo',
        'enunciado',
        'dificultad',
        'bloom',
        'puntos',
        'imagen_url',
        'opcion_1',
        'opcion_2',
        'opcion_3',
        'opcion_4',
        'correctas',
        'test_code',
    ]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = bold_center
        c.alignment = center

    for row_offset, row_vals in enumerate(_example_data_rows(subjects), start=2):
        for col, v in enumerate(row_vals, 1):
            ws.cell(row=row_offset, column=col, value=v).alignment = wrap

    # A=materia, B=tipo, D=dificultad, E=bloom
    _add_list_validation(ws, 'A', sub_name_range)
    _add_list_validation(ws, 'B', _inline_list_formula(TYPE_OPTIONS_ES))
    _add_list_validation(ws, 'D', _inline_list_formula(DIFF_OPTIONS_ES))
    _add_list_validation(ws, 'E', _inline_list_formula(BLOOM_OPTIONS_ES))

    wb.active = ws

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
