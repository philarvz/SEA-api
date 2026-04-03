"""
Exams module views.
Implements CRUD endpoints for Exam management.
All endpoints are restricted to users with the 'teacher' or 'admin' role.
PATCH is reserved exclusively for status changes; full edits use PUT.
"""

from io import BytesIO

from loguru import logger
from django.http import HttpResponse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import openpyxl
from openpyxl.styles import Font, Alignment

from .models import Exam
from .serializers import (
    ExamSerializer,
    ExamCreateSerializer,
    ExamUpdateSerializer,
    ExamStatusSerializer,
)
from .services import ExamService
from apps.academic.permissions import IsTeacherOrAdmin
from utils.responses import success_response, error_response


# Error message constants
MSG_INVALID_DATA = 'Datos inválidos.'
MSG_EXAM_NOT_FOUND = 'Examen no encontrado.'
MSG_NO_PERMISSION = 'No tiene permiso para acceder a este examen.'


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

        exam = ExamService.change_status(exam, serializer.validated_data['status'])
        state = 'activado' if exam.status else 'desactivado'
        return success_response(
            {'id_exam': exam.pk, 'status': exam.status},
            f'Examen {state} exitosamente.',
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
