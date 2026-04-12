"""
Question bank API: CRUD, Excel upload, template download.
"""

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from loguru import logger
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from drf_spectacular.types import OpenApiTypes

from apps.academic.permissions import IsTeacherOrAdmin

from .models import Question, Answer, CodeQuestion
from .serializers import (
    QuestionSerializer,
    QuestionListSerializer,
)
from .excel_upload import (
    normalize_header_row,
    build_column_maps,
    validate_required_columns,
    get_cell,
    parse_difficulty,
    parse_bloom,
    collect_options_from_row,
    resolve_subject_id,
    parse_points,
    worksheet_for_question_import,
    parse_question_type,
)
from .template_workbook import build_questions_template_workbook
from utils.responses import error_response, success_response


class QuestionPagination:
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    @classmethod
    def paginate(cls, request, queryset):
        from rest_framework.pagination import PageNumberPagination

        class P(PageNumberPagination):
            page_size = cls.page_size
            page_size_query_param = cls.page_size_query_param
            max_page_size = cls.max_page_size

        paginator = P()
        page = paginator.paginate_queryset(queryset, request)
        return page, paginator


def _paginated_payload(request, queryset, serializer_class):
    page, paginator = QuestionPagination.paginate(request, queryset)
    if page is None:
        ser = serializer_class(queryset, many=True)
        count = queryset.count()
        return {
            'results': ser.data,
            'pagination': {
                'count': count,
                'page': 1,
                'page_size': count,
                'total_pages': 1,
                'next': None,
                'previous': None,
            },
        }
    ser = serializer_class(page, many=True)
    page_size = paginator.get_page_size(request) or paginator.page_size
    return {
        'results': ser.data,
        'pagination': {
            'count': paginator.page.paginator.count,
            'page': paginator.page.number,
            'page_size': page_size,
            'total_pages': paginator.page.paginator.num_pages,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
        },
    }


_PATH_ID = OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH, description='ID de la pregunta')


@extend_schema_view(
    retrieve=extend_schema(parameters=[_PATH_ID]),
    update=extend_schema(parameters=[_PATH_ID]),
    partial_update=extend_schema(parameters=[_PATH_ID]),
    destroy=extend_schema(parameters=[_PATH_ID]),
)
class QuestionViewSet(ModelViewSet):
    """
    /questions/ CRUD + upload, template.
    """

    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]
    parser_classes = [JSONParser, MultiPartParser]
    lookup_field = 'id_question'
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        qs = (
            Question.objects.select_related('id_subject', 'modified_by')
            .prefetch_related('answers')
            .order_by('-id_question')
        )
        qtype = self.request.query_params.get('type')
        diff = self.request.query_params.get('difficulty')
        subject = self.request.query_params.get('id_subject')
        if qtype:
            qs = qs.filter(question_type=qtype)
        if diff:
            qs = qs.filter(difficulty=diff)
        if subject:
            qs = qs.filter(id_subject_id=subject)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return QuestionListSerializer
        return QuestionSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        payload = _paginated_payload(request, queryset, QuestionListSerializer)
        return success_response(payload)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        ser = QuestionSerializer(instance)
        return success_response(ser.data)

    def create(self, request, *args, **kwargs):
        ser = QuestionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        logger.info('Question created | user={} id={}', request.user.pk, instance.pk)
        out = QuestionSerializer(instance)
        return success_response(out.data, 'Pregunta creada.', status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        ser = QuestionSerializer(instance, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        logger.info('Question updated | user={} id={}', request.user.pk, instance.pk)
        return success_response(QuestionSerializer(instance).data, 'Pregunta actualizada.')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return error_response(
                'La pregunta está asociada a un examen y no puede eliminarse.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        logger.info('Question deleted | user={} id={}', request.user.pk, kwargs.get('pk'))
        return success_response({'id': instance.pk}, 'Pregunta eliminada.')

    @extend_schema(
        summary='Subir preguntas (Excel)',
        parameters=[
            OpenApiParameter('file', OpenApiTypes.BINARY, required=True),
        ],
    )
    @action(detail=False, methods=['post'], url_path='upload', parser_classes=[MultiPartParser])
    def upload(self, request):
        up = request.FILES.get('file')
        if not up:
            return error_response('Debe adjuntar un archivo .xlsx en el campo "file".')
        if not up.name.lower().endswith('.xlsx'):
            return error_response('Solo se aceptan archivos .xlsx.')

        try:
            wb = load_workbook(up, read_only=True, data_only=True)
        except Exception as exc:
            logger.warning('Excel upload parse error: {}', exc)
            return error_response('No se pudo leer el archivo Excel.')

        ws = worksheet_for_question_import(wb)
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        if not rows:
            return error_response('El archivo está vacío.')

        headers_norm = normalize_header_row(rows[0])
        col_by_canon, col_by_header = build_column_maps(headers_norm)
        req_err = validate_required_columns(col_by_canon)
        if req_err:
            return error_response(req_err)

        total = 0
        created = 0
        errors = []

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or all(v is None or str(v).strip() == '' for v in row):
                continue
            total += 1

            try:
                text = get_cell(row, col_by_canon.get('question_text'))
                if not text:
                    raise ValueError('El enunciado (question_text / enunciado) está vacío.')

                qtype = parse_question_type(get_cell(row, col_by_canon.get('type'), 'MULTIPLE_CHOICE'))
                subject_id = resolve_subject_id(row, col_by_canon, request.user)

                options = collect_options_from_row(row, col_by_header)
                if not options and 'options' in col_by_canon:
                    options_raw = get_cell(row, col_by_canon['options'], '') or ''
                    options = [p.strip() for p in str(options_raw).split(',') if p.strip()]

                correct_raw = str(
                    get_cell(row, col_by_canon.get('correct_answers'), '') or ''
                )
                difficulty = parse_difficulty(
                    get_cell(row, col_by_canon.get('difficulty'), 'medium')
                )
                bloom = parse_bloom(
                    get_cell(row, col_by_canon.get('bloom_level'), 'remember')
                )
                image_url = get_cell(row, col_by_canon.get('image_url'), '') or ''
                test_code = get_cell(row, col_by_canon.get('test_code'), '') or ''
                points = parse_points(get_cell(row, col_by_canon.get('points'), 1))

                with transaction.atomic():
                    q = Question.objects.create(
                        id_subject_id=subject_id,
                        statement=str(text),
                        question_type=qtype,
                        difficulty=difficulty,
                        bloom_level=bloom,
                        image_url=image_url or None,
                        points=points,
                        status=True,
                    )

                    if qtype in ('MULTIPLE_CHOICE', 'MULTIPLE_SELECTION'):
                        if len(options) < 2 or len(options) > 4:
                            raise ValueError('Se requieren entre 2 y 4 opciones (separadas por coma).')
                        correct_indices = set()
                        for part in correct_raw.split(','):
                            part = part.strip()
                            if not part:
                                continue
                            if part.isdigit():
                                correct_indices.add(int(part) - 1)
                            else:
                                for i, opt in enumerate(options):
                                    if opt.lower() == part.lower():
                                        correct_indices.add(i)
                                        break
                        if qtype == 'MULTIPLE_CHOICE' and len(correct_indices) != 1:
                            raise ValueError('Para MULTIPLE_CHOICE indique exactamente un índice correcto (1..n).')
                        if qtype == 'MULTIPLE_SELECTION' and len(correct_indices) < 1:
                            raise ValueError('Indique al menos una respuesta correcta.')
                        for i, opt in enumerate(options):
                            Answer.objects.create(
                                id_question=q,
                                answer_text=opt,
                                is_correct=i in correct_indices,
                            )
                    elif qtype == 'OPEN':
                        pass
                    elif qtype == 'CODE':
                        tests = [test_code] if test_code else []
                        if not tests:
                            raise ValueError('test_code es obligatorio para tipo CODE.')
                        CodeQuestion.objects.create(
                            question=q,
                            language='python',
                            test_cases=tests,
                        )
                    else:
                        raise ValueError(f'Tipo no soportado: {qtype}')

                created += 1
            except Exception as exc:
                errors.append({'row': row_idx, 'error': str(exc)})

        return success_response(
            {
                'total_rows': total,
                'created': created,
                'errors': errors,
            },
            'Carga procesada.',
        )

    @extend_schema(
        summary='Descargar plantilla Excel',
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=['get'], url_path='template')
    def template(self, request):
        data = build_questions_template_workbook(request.user)
        resp = HttpResponse(
            data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resp['Content-Disposition'] = 'attachment; filename="plantilla_preguntas.xlsx"'
        return resp
