"""
Exams module views.
Implements CRUD endpoints for Exam management.
All endpoints are restricted to users with the 'teacher' or 'admin' role.
PATCH is reserved exclusively for status changes; full edits use PUT.
"""

import hashlib
import re
from io import BytesIO
from urllib.parse import quote

from loguru import logger
from django.http import HttpResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import openpyxl
from openpyxl.styles import Font, Alignment

from rest_framework.throttling import UserRateThrottle

from .models import Exam, ExamQuestion, ExamAssignment
from .serializers import (
    ExamSerializer,
    ExamCreateSerializer,
    ExamUpdateSerializer,
    ExamStatusSerializer,
    ExamSecureModeSerializer,
    ExamAssignSerializer,
    ExamAssignmentGroupSummarySerializer,
    ExamGroupStatsSerializer,
    GroupStudentGradeSerializer,
    GroupStudentsQuerySerializer,
    MyAssignmentSerializer,
    MyAssignmentQuerySerializer,
    CreatedByMeExamSerializer,
    CreatedByMeQuerySerializer,
    ExamQuestionsReplaceSerializer,
    serialize_exam_question_link,
)
from .services import ExamService, ExamAssignmentService
from apps.academic.permissions import IsTeacherOrAdmin, IsStudent
from utils.responses import success_response, error_response


# Error message constants
MSG_INVALID_DATA = 'Datos inválidos.'
MSG_EXAM_NOT_FOUND = 'Examen no encontrado.'
MSG_NO_PERMISSION = 'No tiene permiso para acceder a este examen.'
MSG_GROUP_NOT_ASSIGNED = 'El grupo no está asignado a este examen.'


class ExamPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def paginated_exam_response(request, queryset):
    """Paginate queryset and return standardised success response."""
    paginator = ExamPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = ExamSerializer(page, many=True)
    page_size = paginator.get_page_size(request) or paginator.page_size

    payload = {
        'results': serializer.data,
        'pagination': {
            'count': paginator.page.paginator.count,
            'page': paginator.page.number,
            'page_size': page_size,
            'total_pages': paginator.page.paginator.num_pages,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
        },
    }
    return success_response(payload)


def _get_user_role(request):
    """Extract role from JWT or user model."""
    role = getattr(request.user, 'role', None)
    if role is None and request.auth is not None:
        role = request.auth.get('role')
    return role


def _deterministic_shuffle(items, seed_str):
    """
    Deterministically reorder items based on a seed string using cryptographic hashing.
    This provides reproducible shuffling without using pseudorandom generators.
    Each unique seed produces a unique but consistent order.
    """
    if len(items) <= 1:
        return items
    
    # Create a list of (item, sort_key) tuples
    indexed_items = []
    for i, item in enumerate(items):
        # Generate a hash-based sort key for each item
        hash_input = f"{seed_str}-{i}".encode('utf-8')
        hash_value = hashlib.sha256(hash_input).hexdigest()
        indexed_items.append((item, hash_value))
    
    # Sort by hash value to get deterministic ordering
    indexed_items.sort(key=lambda x: x[1])
    return [item for item, _ in indexed_items]


def _can_access_exam(request, exam):
    """Teachers can only access their own exams. Compare by pk to handle TokenUser."""
    role = _get_user_role(request)
    if role == 'teacher' and exam.id_teacher_id != request.user.pk:
        return False
    return True


# ---------------------------------------------------------------------------
# List + Create
# ---------------------------------------------------------------------------

class ExamListCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar exámenes',
        tags=['Exámenes'],
        parameters=[
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('id_subject', OpenApiTypes.INT, description='Filtrar por materia', required=False),
            OpenApiParameter('difficulty_level', OpenApiTypes.STR, description='Filtrar por dificultad (easy, medium, hard)', required=False),
            OpenApiParameter('search', OpenApiTypes.STR, description='Buscar por nombre o materia', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: ExamSerializer(many=True)},
    )
    def get(self, request):
        queryset = ExamService.get_filtered_queryset(request.query_params, request.user)
        logger.info('Exams listed | user={} count={}', request.user.pk, queryset.count())
        return paginated_exam_response(request, queryset)

    @extend_schema(
        summary='Crear examen',
        tags=['Exámenes'],
        request=ExamCreateSerializer,
        responses={201: ExamSerializer, 400: OpenApiResponse(description='Datos inválidos')},
    )
    def post(self, request):
        serializer = ExamCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Exam creation rejected | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)

        try:
            exam = ExamService.create_exam(serializer.validated_data, request.user)
        except DjangoValidationError as exc:
            logger.warning('Exam model validation failed | detail={}', exc.message_dict)
            return error_response(MSG_INVALID_DATA, exc.message_dict)

        return success_response(
            ExamSerializer(exam).data,
            'Examen creado exitosamente.',
            status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Detail + Update
# ---------------------------------------------------------------------------

class ExamDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def _get_exam(self, pk):
        try:
            return Exam.objects.select_related('id_subject', 'id_teacher').get(pk=pk)
        except Exam.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener examen',
        tags=['Exámenes'],
        responses={200: ExamSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def get(self, request, pk):
        exam = self._get_exam(pk)
        if not exam:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)
        return success_response(ExamSerializer(exam).data)

    @extend_schema(
        summary='Actualizar examen',
        tags=['Exámenes'],
        request=ExamUpdateSerializer,
        responses={200: ExamSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def put(self, request, pk):
        exam = self._get_exam(pk)
        if not exam:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        serializer = ExamUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Exam update rejected | id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)

        try:
            exam = ExamService.update_exam(exam, serializer.validated_data)
        except DjangoValidationError as exc:
            logger.warning('Exam model validation failed | id={} detail={}', pk, exc.message_dict)
            return error_response(MSG_INVALID_DATA, exc.message_dict)

        return success_response(ExamSerializer(exam).data, 'Examen actualizado exitosamente.')


# ---------------------------------------------------------------------------
# Exam ↔ Question bank (ExamQuestion)
# ---------------------------------------------------------------------------

class ExamQuestionsView(APIView):
    """
    GET: lista preguntas vinculadas (orden estable por id_exam_question; no es orden de examen para el alumno).
    PUT: reemplaza el conjunto de preguntas; el orden del array solo afecta el orden de esa lista administrativa.
    Todas las preguntas deben ser de la misma materia que el examen.
    """
    permission_classes = [IsAuthenticated]

    def _get_exam(self, exam_id):
        try:
            return Exam.objects.select_related('id_subject', 'id_teacher').get(pk=exam_id)
        except Exam.DoesNotExist:
            return None

    def _get_student_assignment(self, request, exam):
        """Return assignment object for current student in the target exam, if any."""
        return ExamAssignment.objects.filter(
            exam_id=exam.id_exam,
            student_id=request.user.pk,
        ).first()

    @extend_schema(
        summary='Listar preguntas del examen',
        tags=['Exámenes'],
        responses={200: OpenApiResponse(description='Lista ordenada de preguntas vinculadas')},
    )
    def get(self, request, exam_id):
        exam = self._get_exam(exam_id)
        if not exam:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        role = _get_user_role(request)
        student_assignment = None
        if role in ('teacher', 'admin'):
            if not _can_access_exam(request, exam):
                return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)
        elif role == 'student':
            student_assignment = self._get_student_assignment(request, exam)
            if not student_assignment:
                return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)
        else:
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        eqs = (
            exam.exam_questions.select_related('id_question')
            .prefetch_related('id_question__answers', 'id_question__code_question')
            .order_by('id_exam_question')
        )
        data = [serialize_exam_question_link(eq) for eq in eqs]

        # Students receive a per-assignment shuffled order so different students
        # get different sequences while each student keeps a stable order.
        if role == 'student' and student_assignment and len(data) > 1:
            seed = f"{student_assignment.pk}-{student_assignment.student_id}-{exam.id_exam}"
            data = _deterministic_shuffle(data, seed)

        return success_response({'questions': data})

    @extend_schema(
        summary='Asignar / reordenar preguntas del examen',
        tags=['Exámenes'],
        request=ExamQuestionsReplaceSerializer,
        responses={200: OpenApiResponse(description='Lista actualizada')},
    )
    def put(self, request, exam_id):
        exam = self._get_exam(exam_id)
        if not exam:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        role = _get_user_role(request)
        if role not in ('teacher', 'admin'):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)
        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        serializer = ExamQuestionsReplaceSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)

        try:
            ExamService.sync_exam_questions(exam, serializer.validated_data['question_ids'])
        except ValueError as exc:
            logger.warning('Exam questions sync rejected | exam={} err={}', exam_id, exc)
            return error_response(str(exc))

        eqs = (
            ExamQuestion.objects.filter(id_exam=exam)
            .select_related('id_question')
            .prefetch_related('id_question__answers', 'id_question__code_question')
            .order_by('id_exam_question')
        )
        data = [serialize_exam_question_link(eq) for eq in eqs]
        return success_response({'questions': data}, 'Preguntas del examen actualizadas.')


# ---------------------------------------------------------------------------
# Status change (soft toggle)
# ---------------------------------------------------------------------------

class ExamStatusView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Cambiar estado de examen',
        tags=['Exámenes'],
        request=ExamStatusSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def patch(self, request, pk):
        try:
            exam = Exam.objects.get(pk=pk)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        serializer = ExamStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)

        new_status = serializer.validated_data['status']

        # Activation guard: verify all conditions before allowing status=True
        if new_status:
            errors = ExamService.validate_can_activate(exam)
            if errors:
                return error_response(
                    'No se puede activar el examen porque no cumple todos los requisitos: El examen debe estar asignado a algun grupo, debe de tener al menos una pregunta, y al menos un grupo debe tener un período de disponibilidad válido.',
                    {'requisitos': errors},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        exam = ExamService.change_status(exam, new_status)
        state = 'activado' if exam.status else 'desactivado'
        return success_response(
            {'id_exam': exam.pk, 'status': exam.status},
            f'Examen {state} exitosamente.',
        )


# ---------------------------------------------------------------------------
# Secure mode toggle
# ---------------------------------------------------------------------------

class ExamSecureModeView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Activar/Desactivar modo seguro',
        tags=['Exámenes'],
        request=ExamSecureModeSerializer,
        responses={
            200: OpenApiResponse(description='Modo seguro actualizado'),
            404: OpenApiResponse(description='No encontrado'),
        },
    )
    def patch(self, request, pk):
        try:
            exam = Exam.objects.get(pk=pk)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        serializer = ExamSecureModeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)

        exam = ExamService.change_secure_mode(exam, serializer.validated_data['secure_mode'])
        state = 'activado' if exam.secure_mode else 'desactivado'
        return success_response(
            {'id_exam': exam.pk, 'secure_mode': exam.secure_mode},
            f'Modo seguro {state} exitosamente.',
        )


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

class ExamDeleteView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Eliminar examen (lógico)',
        tags=['Exámenes'],
        responses={200: OpenApiResponse(description='Eliminado lógicamente'), 404: OpenApiResponse(description='No encontrado')},
    )
    def delete(self, request, pk):
        try:
            exam = Exam.objects.get(pk=pk)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        ExamService.soft_delete(exam)
        return success_response(
            {'id_exam': exam.pk, 'status': False},
            'Examen eliminado exitosamente.',
        )


# ---------------------------------------------------------------------------
# Template download (existing functionality)
# ---------------------------------------------------------------------------

class QuestionTemplateDownloadView(APIView):
    """
    View to generate and download a question template Excel file
    """
    @extend_schema(
        summary="Descargar Plantilla de Preguntas", 
        tags=['Plantillas de Preguntas'],
        description="Genera y descarga un archivo Excel con una plantilla para ingresar preguntas de examen.",
        responses={
            200: OpenApiTypes.BINARY,
            400: OpenApiResponse(description="Solicitud inválida")
        }
    )
    def get(self, request, *args, **kwargs):
        # Create a new workbook and select the active worksheet
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Plantilla de Preguntas"

        # Define headers
        headers = [
            "Materia",
            "Enunciado de la Pregunta",
            "Nivel Bloom",
            "Respuesta 1",
            "¿Es Correcta 1?",
            "Respuesta 2",
            "¿Es Correcta 2?",
            "Respuesta 3",
            "¿Es Correcta 3?",
            "Respuesta 4",
            "¿Es Correcta 4?",
            "Respuesta 5",
            "¿Es Correcta 5?"
        ]

        # Add headers to the first row
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # Add some example data in the second row
        example_data = [
            "Matemáticas",
            "¿Cuál es la capital de Francia?",
            "remember",
            "París",
            "VERDADERO",
            "Londres",
            "FALSO",
            "Madrid",
            "FALSO",
            "Roma",
            "FALSO",
            "Berlín",
            "FALSO"
        ]

        for col_num, value in enumerate(example_data, 1):
            cell = ws.cell(row=2, column=col_num, value=value)
            cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # Add instructions in the third row
        instructions = [
            "INSTRUCCIONES:",
            "1. Complete los campos requeridos para cada pregunta",
            "2. El campo 'Materia' debe coincidir con una materia existente",
            "3. Los niveles Bloom válidos son: remember, understand, apply, analyze, evaluate, create",
            "4. Para las respuestas, use VERDADERO/FALSO en la columna '¿Es Correcta?'",
            "5. Al menos una respuesta debe ser VERDADERO por pregunta",
            "6. Puede dejar respuestas en blanco si no son necesarias"
        ]

        for col_num, instruction in enumerate(instructions, 1):
            if col_num <= len(headers):
                cell = ws.cell(row=3, column=col_num, value=instruction)
                cell.font = Font(italic=True, color="666666")
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except (TypeError, AttributeError):
                    pass
            adjusted_width = min(max_length + 2, 50)  # Max width of 50
            ws.column_dimensions[column].width = adjusted_width

        # Set row height for better readability
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 40
        ws.row_dimensions[3].height = 60

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="plantilla_preguntas.xlsx"'

        # Save workbook to response
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()

        return response


# ---------------------------------------------------------------------------
# Group-level stats for an exam
# ---------------------------------------------------------------------------

class ExamGroupStatsView(APIView):
    """
    GET /api/exams/{exam_id}/stats/groups/
    Returns per-group statistics for ALL groups assigned to the exam.
    Groups with zero students are included.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Estadísticas por grupo de un examen (todos los grupos)',
        tags=['Estadísticas de Exámenes'],
        responses={
            200: ExamGroupStatsSerializer(many=True),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen no encontrado'),
        },
    )
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        stats = ExamAssignmentService.get_group_stats(exam)
        serializer = ExamGroupStatsSerializer(stats, many=True)
        return success_response(serializer.data)


class ExamGroupStatsByGroupView(APIView):
    """
    GET /api/exams/{exam_id}/stats/groups/{group_id}/
    Returns statistics for a single group within the exam.
    Used by the tab-based grades view to load one group at a time.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Estadísticas de un grupo específico en un examen',
        tags=['Estadísticas de Exámenes'],
        responses={
            200: ExamGroupStatsSerializer(),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen o grupo no encontrado'),
        },
    )
    def get(self, request, exam_id, group_id):
        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        stats = ExamAssignmentService.get_group_stats(exam, group_id=group_id)
        if not stats:
            return error_response(
                'El grupo no está asignado a este examen.',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = ExamGroupStatsSerializer(stats[0])
        return success_response(serializer.data)


# ---------------------------------------------------------------------------
# Students grades per group for an exam
# ---------------------------------------------------------------------------

class ExamGroupStudentsView(APIView):
    """
    GET /api/exams/{exam_id}/groups/{group_id}/students/
    Returns the list of students assigned to the exam within the given group,
    including their current score and status.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Calificaciones de estudiantes por grupo en un examen',
        tags=['Calificaciones de Exámenes'],
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
            OpenApiParameter(
                'status', OpenApiTypes.STR,
                description='Filtrar por estado (pending, in_progress, completed)',
                required=False,
                enum=['pending', 'in_progress', 'completed'],
            ),
            OpenApiParameter(
                'search', OpenApiTypes.STR,
                description='Buscar por nombre, apellido o matrícula del alumno',
                required=False,
            ),
        ],
        responses={
            200: GroupStudentGradeSerializer(many=True),
            400: OpenApiResponse(description='Parámetros inválidos'),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen o grupo no encontrado'),
        },
    )
    def get(self, request, exam_id, group_id):
        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        # Verify the group is actually assigned to this exam
        from .models import ExamGroupAssignment
        if not ExamGroupAssignment.objects.filter(exam=exam, group_id=group_id).exists():
            return error_response(MSG_GROUP_NOT_ASSIGNED, status_code=status.HTTP_404_NOT_FOUND)

        # Validate query params via serializer (Rule 1)
        query_serializer = GroupStudentsQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return error_response('Parámetros inválidos.', query_serializer.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)

        assignments = ExamAssignmentService.get_group_students(
            exam,
            group_id,
            status_filter=query_serializer.validated_data.get('status'),
            search=query_serializer.validated_data.get('search'),
        )

        paginator = ExamPagination()
        page = paginator.paginate_queryset(assignments, request)
        serializer = GroupStudentGradeSerializer(page, many=True)
        page_size = paginator.get_page_size(request) or paginator.page_size

        payload = {
            'results': serializer.data,
            'pagination': {
                'count': paginator.page.paginator.count,
                'page': paginator.page.number,
                'page_size': page_size,
                'total_pages': paginator.page.paginator.num_pages,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
        }
        return success_response(payload)


# ---------------------------------------------------------------------------
# Exam assignment to groups
# ---------------------------------------------------------------------------

class ExamAssignView(APIView):
    """
    GET  /exam-assignments/assign/?exam_id=<id>  — current group assignments for an exam.
    POST /exam-assignments/assign/               — sync (add/remove/update) group assignments.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Consultar grupos asignados a un examen',
        tags=['Asignaciones de Exámenes'],
        parameters=[
            OpenApiParameter('exam_id', OpenApiTypes.INT, description='ID del examen', required=True),
        ],
        responses={
            200: ExamAssignmentGroupSummarySerializer(many=True),
            400: OpenApiResponse(description='Parámetro faltante'),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen no encontrado'),
        },
    )
    def get(self, request):
        raw_exam_id = request.query_params.get('exam_id')
        if not raw_exam_id:
            return error_response('El parámetro exam_id es requerido.')
        try:
            exam_id = int(raw_exam_id)
        except (ValueError, TypeError):
            return error_response('exam_id debe ser un entero válido.')

        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        groups_data = ExamAssignmentService.get_assigned_groups(exam)
        serializer = ExamAssignmentGroupSummarySerializer(groups_data, many=True)
        return success_response(serializer.data)

    @extend_schema(
        summary='Sincronizar grupos asignados a un examen',
        tags=['Asignaciones de Exámenes'],
        request=ExamAssignSerializer,
        responses={
            200: OpenApiResponse(description='Sincronización exitosa'),
            400: OpenApiResponse(description='Error de validación'),
            403: OpenApiResponse(description='Sin permisos'),
        },
    )
    def post(self, request):
        serializer = ExamAssignSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Exam assignment rejected | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)

        exam = serializer.context['_exam']
        groups = serializer.context.get('_groups', [])

        # Ownership: teachers can only assign their own exams
        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        try:
            summary = ExamAssignmentService.sync_exam_groups(
                exam=exam,
                groups=groups,
                available_from=serializer.validated_data['available_from'],
                available_to=serializer.validated_data['available_to'],
                teacher_pk=request.user.pk,
            )
            # Return the updated group list so the frontend can refresh immediately
            assigned_groups = ExamAssignmentService.get_assigned_groups(exam)
            summary['assigned_groups'] = ExamAssignmentGroupSummarySerializer(
                assigned_groups, many=True
            ).data
        except Exception:  # noqa: BLE001
            logger.exception('Unexpected error syncing exam groups | exam={}', exam.pk)
            return error_response(
                'Error al sincronizar las asignaciones.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(summary, 'Asignaciones sincronizadas exitosamente.')


# ---------------------------------------------------------------------------
# Teacher/Admin: Exams created by me
# ---------------------------------------------------------------------------

class _CreatedByMeThrottle(UserRateThrottle):
    """Dedicated throttle scope for teacher/admin created-by-me listing."""
    scope = 'created_by_me'


class CreatedByMeExamsView(APIView):
    """GET /exams/created-by-me — paginated list of exams created by the requester."""
    permission_classes = [IsTeacherOrAdmin]
    throttle_classes = [_CreatedByMeThrottle]

    @extend_schema(
        summary='Mis exámenes creados',
        tags=['Exámenes'],
        parameters=[
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado (true/false)', required=False),
            OpenApiParameter('id_subject', OpenApiTypes.INT, description='Filtrar por materia', required=False),
            OpenApiParameter('difficulty_level', OpenApiTypes.STR, description='Filtrar por dificultad (easy, medium, hard)', required=False),
            OpenApiParameter('search', OpenApiTypes.STR, description='Buscar por nombre o materia', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={
            200: CreatedByMeExamSerializer(many=True),
            400: OpenApiResponse(description='Parámetros inválidos'),
            403: OpenApiResponse(description='Sin permisos'),
        },
    )
    def get(self, request):
        # Rule 1: validate all query-param inputs through a serializer
        query_serializer = CreatedByMeQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return error_response(MSG_INVALID_DATA, query_serializer.errors)

        try:
            queryset = ExamService.get_exams_created_by(
                user_pk=request.user.pk,
                params=query_serializer.validated_data,
            )

            paginator = ExamPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = CreatedByMeExamSerializer(page, many=True)
            page_size = paginator.get_page_size(request) or paginator.page_size

            payload = {
                'results': serializer.data,
                'pagination': {
                    'count': paginator.page.paginator.count,
                    'page': paginator.page.number,
                    'page_size': page_size,
                    'total_pages': paginator.page.paginator.num_pages,
                    'next': paginator.get_next_link(),
                    'previous': paginator.get_previous_link(),
                },
            }
        except Exception:  # noqa: BLE001
            logger.exception('Unexpected error in created-by-me | user={}', request.user.pk)
            return error_response(
                'Error al obtener los exámenes.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            'Created-by-me listed | user={} count={}',
            request.user.pk, paginator.page.paginator.count,
        )
        return success_response(payload)


# ---------------------------------------------------------------------------
# Student: My Assignments
# ---------------------------------------------------------------------------

class _StudentAssignmentThrottle(UserRateThrottle):
    """Dedicated throttle scope for student assignment listing."""
    scope = 'student_assignments'


class MyAssignmentsView(APIView):
    """GET /exam-assignments/my-assignments — student's own exam list."""
    permission_classes = [IsStudent]
    throttle_classes = [_StudentAssignmentThrottle]

    @extend_schema(
        summary='Mis asignaciones de exámenes',
        tags=['Asignaciones de Exámenes'],
        parameters=[
            OpenApiParameter(
                'status', OpenApiTypes.STR,
                description='Filtrar por estado (pending, in_progress, completed)',
                required=False,
            ),
            OpenApiParameter(
                'include_completed', OpenApiTypes.BOOL,
                description='Incluir asignaciones completadas (default: false)',
                required=False,
            ),
        ],
        responses={
            200: MyAssignmentSerializer(many=True),
            400: OpenApiResponse(description='Parámetros inválidos'),
            403: OpenApiResponse(description='No es alumno'),
        },
    )
    def get(self, request):
        # Rule 1: validate all query-param inputs through a serializer
        query_serializer = MyAssignmentQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return error_response(MSG_INVALID_DATA, query_serializer.errors)

        try:
            queryset = ExamAssignmentService.get_student_assignments(
                student_pk=request.user.pk,
                params=query_serializer.validated_data,
            )
            # Evaluate count before serialization to keep a single DB round-trip
            count = queryset.count()
            serializer = MyAssignmentSerializer(queryset, many=True)
        except Exception:  # noqa: BLE001
            # Rule 9: never expose internal error details to the client
            logger.exception('Unexpected error listing assignments | student={}', request.user.pk)
            return error_response(
                'Error al obtener las asignaciones.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('Student assignments listed | student={} count={}', request.user.pk, count)
        return success_response(serializer.data)


# ---------------------------------------------------------------------------
# Grade export (PDF / Excel)
# ---------------------------------------------------------------------------

def _build_export_filename(exam, group, ext: str) -> str:
    """
    Build a sanitised export filename:
      [exam_name]-calificaciones-[academic_level][group_letter] (Gen [year]).[ext]

    Characters forbidden in filenames and HTTP headers (null bytes, newlines,
    path separators, Windows reserved chars) are stripped before use.
    The filename* parameter uses RFC 5987 percent-encoding for full Unicode support.
    """
    from apps.academic.services import PeriodService

    level = PeriodService.sync_group_academic_level(group)
    gen_year = group.id_generation.year if group.id_generation else ''
    group_part = f'{level}{group.group_letter} (Gen {gen_year})'

    raw_exam = exam.name or exam.title or 'examen'
    # Strip characters that are invalid in filenames or HTTP header values
    _UNSAFE = r'[\x00\r\n/\\:*?"<>|]'
    safe_exam = re.sub(_UNSAFE, '', raw_exam).strip()[:80]
    safe_group = re.sub(_UNSAFE, '', group_part).strip()[:40]

    return f'{safe_exam}-calificaciones-{safe_group}.{ext}'


class _GradeExportThrottle(UserRateThrottle):
    """Dedicated throttle scope for grade file exports."""
    scope = 'grade_export'


class _BaseGradeExportView(APIView):
    """
    Shared logic for PDF and Excel grade export endpoints.
    Validates exam existence, ownership, and group assignment.
    """
    permission_classes = [IsTeacherOrAdmin]
    throttle_classes = [_GradeExportThrottle]

    def _validate_exam_group(self, request, exam_id, group_id):
        """
        Return (exam, group) tuple or an error Response.
        """
        from apps.academic.models import Group

        try:
            exam = Exam.objects.select_related('id_subject', 'id_teacher').get(pk=exam_id)
        except Exam.DoesNotExist:
            return error_response(MSG_EXAM_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not _can_access_exam(request, exam):
            return error_response(MSG_NO_PERMISSION, status_code=status.HTTP_403_FORBIDDEN)

        from .models import ExamGroupAssignment as EGA
        if not EGA.objects.filter(exam=exam, group_id=group_id).exists():
            return error_response(MSG_GROUP_NOT_ASSIGNED, status_code=status.HTTP_404_NOT_FOUND)

        try:
            group = Group.objects.select_related('id_generation').get(pk=group_id)
        except Group.DoesNotExist:
            return error_response('Grupo no encontrado.', status_code=status.HTTP_404_NOT_FOUND)

        return exam, group


class ExamGradeExportExcelView(_BaseGradeExportView):
    """
    GET /api/exams/{exam_id}/grades/groups/{group_id}/export/excel/
    Downloads an Excel file with the grades for the specified exam + group.
    """

    @extend_schema(
        summary='Exportar calificaciones a Excel',
        tags=['Exportación de Calificaciones'],
        responses={
            200: OpenApiResponse(description='Archivo Excel (.xlsx)'),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen o grupo no encontrado'),
        },
    )
    def get(self, request, exam_id, group_id):
        result = self._validate_exam_group(request, exam_id, group_id)
        if not isinstance(result, tuple):
            return result

        exam, group = result

        from .services import GradeExportService
        buf = GradeExportService.generate_excel(exam, group)

        filename = _build_export_filename(exam, group, 'xlsx')

        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        )
        buf.close()

        logger.info(
            'Grade Excel exported | exam={} group={} user={}',
            exam_id, group_id, request.user.pk,
        )
        return response


class ExamGradeExportPDFView(_BaseGradeExportView):
    """
    GET /api/exams/{exam_id}/grades/groups/{group_id}/export/pdf/
    Downloads a PDF file with the grades for the specified exam + group.
    """

    @extend_schema(
        summary='Exportar calificaciones a PDF',
        tags=['Exportación de Calificaciones'],
        responses={
            200: OpenApiResponse(description='Archivo PDF'),
            403: OpenApiResponse(description='Sin permisos'),
            404: OpenApiResponse(description='Examen o grupo no encontrado'),
        },
    )
    def get(self, request, exam_id, group_id):
        result = self._validate_exam_group(request, exam_id, group_id)
        if not isinstance(result, tuple):
            return result

        exam, group = result

        from .services import GradeExportService
        buf = GradeExportService.generate_pdf(exam, group)

        filename = _build_export_filename(exam, group, 'pdf')

        response = HttpResponse(
            buf.getvalue(),
            content_type='application/pdf',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        )
        buf.close()

        logger.info(
            'Grade PDF exported | exam={} group={} user={}',
            exam_id, group_id, request.user.pk,
        )
        return response
