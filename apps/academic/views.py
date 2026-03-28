"""
Academic module views.
Implements endpoints for Generation, Period, Group and Subject management.
All endpoints are restricted to users with the 'teacher' or 'admin' role.
PATCH is reserved exclusively for status changes; full edits use PUT.
"""

from loguru import logger
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import Generation, Period, Group, Subject, Unit
from .serializers import (
    GenerationSerializer,
    PeriodSerializer,
    GroupSerializer,
    GroupCreateSerializer,
    GroupUpdateSerializer,
    SubjectSerializer,
    UnitSerializer,
    StatusUpdateSerializer,
    AssignStudentSerializer,
)
from .permissions import IsTeacherOrAdmin
from .services import PeriodService
from apps.users.models import StudentProfile
from utils.responses import success_response, error_response


# Error message constants
MSG_INVALID_DATA = 'Datos inválidos.'
MSG_GENERATION_NOT_FOUND = 'Generación no encontrada.'
MSG_PERIOD_NOT_FOUND = 'Periodo no encontrado.'
MSG_GROUP_NOT_FOUND = 'Grupo no encontrado.'
MSG_SUBJECT_NOT_FOUND = 'Materia no encontrada.'


class CatalogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def paginated_success_response(request, queryset, serializer_class):
    paginator = CatalogPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)
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
# Generation views  (GEN-001, GEN-002)
# ---------------------------------------------------------------------------

class GenerationListCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar generaciones',
        tags=['Generaciones'],
        parameters=[
            OpenApiParameter('id_generation', OpenApiTypes.INT, description='Filtrar por ID de generación', required=False),
            OpenApiParameter('year', OpenApiTypes.INT, description='Filtrar por año', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: GenerationSerializer(many=True)},
    )
    def get(self, request):
        queryset = Generation.objects.all()
        id_generation = request.query_params.get('id_generation')
        year = request.query_params.get('year')
        status_param = request.query_params.get('status')
        if id_generation:
            queryset = queryset.filter(id_generation=id_generation)
        if year:
            queryset = queryset.filter(year=year)
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))
        logger.info('Generaciones consultadas | count={}', queryset.count())
        return paginated_success_response(request, queryset, GenerationSerializer)

    @extend_schema(
        summary='Registrar generación',
        tags=['Generaciones'],
        request=GenerationSerializer,
        responses={201: GenerationSerializer},
    )
    def post(self, request):
        serializer = GenerationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Registro de generación rechazado | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            instance = serializer.save()
            logger.info('Generación registrada | id={} year={}', instance.pk, instance.year)
        except IntegrityError as exc:
            logger.error('IntegrityError al registrar generación | detail={}', exc)
            return error_response(
                'No se pudo registrar la generación por conflicto de integridad.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Generación registrada exitosamente.', status.HTTP_201_CREATED)


class GenerationDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def _get_generation(self, pk):
        try:
            return Generation.objects.get(pk=pk)
        except Generation.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener generación',
        tags=['Generaciones'],
        responses={200: GenerationSerializer, 404: OpenApiResponse(description='No encontrada')},
    )
    def get(self, request, pk):
        generation = self._get_generation(pk)
        if not generation:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        return success_response(GenerationSerializer(generation).data)

    @extend_schema(
        summary='Actualizar generación',
        tags=['Generaciones'],
        request=GenerationSerializer,
        responses={200: GenerationSerializer, 404: OpenApiResponse(description='No encontrada')},
    )
    def put(self, request, pk):
        generation = self._get_generation(pk)
        if not generation:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GenerationSerializer(generation, data=request.data)
        if not serializer.is_valid():
            logger.warning('Actualización de generación rechazada | id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            serializer.save()
            logger.info('Generación actualizada | id={}', pk)
        except IntegrityError as exc:
            logger.error('IntegrityError al actualizar generación | id={} detail={}', pk, exc)
            return error_response(
                'No se pudo actualizar la generación por conflicto de integridad.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Generación actualizada exitosamente.')


class GenerationStatusView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Cambiar estado de generación',
        tags=['Generaciones'],
        request=StatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrada')},
    )
    def patch(self, request, pk):
        try:
            generation = Generation.objects.get(pk=pk)
        except Generation.DoesNotExist:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        generation.status = serializer.validated_data['status']
        generation.save(update_fields=['status'])
        state = 'activada' if generation.status else 'desactivada'
        logger.info('Generación {} | id={}', state, pk)
        return success_response(
            {'id_generation': generation.pk, 'status': generation.status},
            f'Generación {state} exitosamente.',
        )


# ---------------------------------------------------------------------------
# Period views  (PER-001, PER-002, PER-003)
# ---------------------------------------------------------------------------

class PeriodListCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar periodos académicos',
        tags=['Periodos'],
        parameters=[
            OpenApiParameter('year', OpenApiTypes.INT, description='Filtrar por año', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: PeriodSerializer(many=True)},
    )
    def get(self, request):
        queryset = Period.objects.all()
        year = request.query_params.get('year')
        status_param = request.query_params.get('status')
        if year:
            queryset = queryset.filter(year=year)
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))
        logger.info('Periodos consultados | count={}', queryset.count())
        return paginated_success_response(request, queryset, PeriodSerializer)

    @extend_schema(
        summary='Registrar periodo académico',
        tags=['Periodos'],
        request=PeriodSerializer,
        responses={201: PeriodSerializer},
    )
    def post(self, request):
        serializer = PeriodSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Registro de periodo rechazado | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            instance = serializer.save()
            logger.info('Periodo registrado | id={} year={} name={}', instance.pk, instance.year, instance.period_name)
        except IntegrityError as exc:
            logger.error('IntegrityError al registrar periodo | detail={}', exc)
            return error_response(
                'Ya existe un periodo con ese nombre para el año indicado.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Periodo registrado exitosamente.', status.HTTP_201_CREATED)


class PeriodCurrentView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Obtener periodo académico actual',
        tags=['Periodos'],
        responses={
            200: PeriodSerializer,
            404: OpenApiResponse(description='No hay periodo activo para la fecha actual'),
        },
    )
    def get(self, request):
        current = PeriodService.get_current_period()
        if not current:
            logger.info('No se encontró periodo activo para la fecha actual')
            return error_response(
                'No se encontró un periodo académico activo para la fecha actual.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        logger.info('Periodo actual detectado | id={} {}', current.pk, current)
        return success_response(PeriodSerializer(current).data)


class PeriodDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def _get_period(self, pk):
        try:
            return Period.objects.get(pk=pk)
        except Period.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener periodo académico',
        tags=['Periodos'],
        responses={200: PeriodSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def get(self, request, pk):
        period = self._get_period(pk)
        if not period:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        return success_response(PeriodSerializer(period).data)

    @extend_schema(
        summary='Actualizar periodo académico',
        tags=['Periodos'],
        request=PeriodSerializer,
        responses={200: PeriodSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def put(self, request, pk):
        period = self._get_period(pk)
        if not period:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = PeriodSerializer(period, data=request.data)
        if not serializer.is_valid():
            logger.warning('Actualización de periodo rechazada | id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            serializer.save()
            logger.info('Periodo actualizado | id={}', pk)
        except IntegrityError as exc:
            logger.error('IntegrityError al actualizar periodo | id={} detail={}', pk, exc)
            return error_response(
                'Ya existe un periodo con ese nombre para el año indicado.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Periodo actualizado exitosamente.')

class PeriodStatusView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Cambiar estado de periodo académico',
        tags=['Periodos'],
        request=StatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def patch(self, request, pk):
        try:
            period = Period.objects.get(pk=pk)
        except Period.DoesNotExist:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        period.status = serializer.validated_data['status']
        period.save(update_fields=['status'])
        state = 'activado' if period.status else 'desactivado'
        logger.info('Periodo {} | id={}', state, pk)
        return success_response(
            {'id_period': period.pk, 'status': period.status},
            f'Periodo {state} exitosamente.',
        )


class PeriodAdvanceGroupsView(APIView):
    """
    Avanza el nivel académico de todos los grupos activos en 1,
    con un límite máximo igual al nivel académico máximo que se encuentra en la tabla Generación.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Avanzar el nivel académico de los grupos activos',
        tags=['Periodos'],
        request=None,
        responses={200: OpenApiResponse(description='Grupos actualizados')},
    )
    def post(self, request, pk):
        try:
            period = Period.objects.get(pk=pk)
        except Period.DoesNotExist:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not period.status:
            return error_response(
                'El periodo especificado está inactivo.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated_count = PeriodService.advance_groups_academic_level()
        logger.info(
            'Nivel académico avanzado | period_id={} groups_updated={}',
            pk, updated_count,
        )
        return success_response(
            {'period_id': pk, 'groups_updated': updated_count},
            f'Nivel académico avanzado exitosamente para {updated_count} grupo(s).',
        )


# ---------------------------------------------------------------------------
# Group views  (GG-001 → GG-004)
# ---------------------------------------------------------------------------

class GroupListCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar grupos académicos',
        tags=['Grupos'],
        parameters=[
            OpenApiParameter('id_generation', OpenApiTypes.INT, description='Filtrar por generación', required=False),
            OpenApiParameter('academic_level', OpenApiTypes.INT, description='Filter by academic level', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: GroupSerializer(many=True)},
    )
    def get(self, request):
        queryset = Group.objects.select_related('id_generation', 'id_period').all()
        id_generation = request.query_params.get('id_generation')
        academic_level = request.query_params.get('academic_level')
        status_param = request.query_params.get('status')
        if id_generation:
            queryset = queryset.filter(id_generation_id=id_generation)
        if academic_level:
            queryset = queryset.filter(academic_level=academic_level)
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))
        logger.info('Grupos consultados | count={}', queryset.count())
        return paginated_success_response(request, queryset, GroupSerializer)

    @extend_schema(
        summary='Registrar grupo académico',
        tags=['Grupos'],
        request=GroupCreateSerializer,
        responses={201: GroupSerializer},
    )
    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Registro de grupo rechazado | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)

        data = serializer.validated_data
        current_period = PeriodService.get_current_period()

        try:
            generation = Generation.objects.get(pk=data['id_generation'])
        except Generation.DoesNotExist:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        try:
            group = Group.objects.create(
                id_generation=generation,
                id_period=current_period,
                group_letter=data['group_letter'],
                academic_level=data['academic_level'],
                status=data.get('status', True),
            )
            logger.info(
                'Group created | id={} letter={} academic_level={} period={}',
                group.pk, group.group_letter, group.academic_level,
                current_period.pk if current_period else None,
            )
        except IntegrityError as exc:
            logger.error('IntegrityError al registrar grupo | detail={}', exc)
            return error_response(
                'Ya existe un grupo con esa letra para la generación indicada.',
                status_code=status.HTTP_409_CONFLICT,
            )

        return success_response(
            GroupSerializer(group).data,
            'Grupo registrado exitosamente.',
            status.HTTP_201_CREATED,
        )


class GroupDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def _get_group(self, pk):
        try:
            return Group.objects.select_related('id_generation', 'id_period').get(pk=pk)
        except Group.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener grupo académico',
        tags=['Grupos'],
        responses={200: GroupSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def get(self, request, pk):
        group = self._get_group(pk)
        if not group:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        return success_response(GroupSerializer(group).data)

    @extend_schema(
        summary='Actualizar grupo académico',
        tags=['Grupos'],
        request=GroupUpdateSerializer,
        responses={200: GroupSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def put(self, request, pk):
        group = self._get_group(pk)
        if not group:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GroupUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Actualización de grupo rechazada | id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        data = serializer.validated_data
        try:
            group.group_letter = data['group_letter']
            group.academic_level = data['academic_level']
            group.status = data['status']
            group.save(update_fields=['group_letter', 'academic_level', 'status'])
            logger.info('Grupo actualizado | id={}', pk)
        except IntegrityError as exc:
            logger.error('IntegrityError al actualizar grupo | id={} detail={}', pk, exc)
            return error_response(
                'Ya existe un grupo con esa letra para la generación indicada.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(GroupSerializer(group).data, 'Grupo actualizado exitosamente.')


class GroupStatusView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Cambiar estado de grupo académico',
        tags=['Grupos'],
        request=StatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def patch(self, request, pk):
        try:
            group = Group.objects.get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        group.status = serializer.validated_data['status']
        group.save(update_fields=['status'])
        state = 'activado' if group.status else 'desactivado'
        logger.info('Grupo {} | id={}', state, pk)
        return success_response(
            {'id_group': group.pk, 'status': group.status},
            f'Grupo {state} exitosamente.',
        )


class GroupAssignStudentView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Asignar alumno a grupo',
        tags=['Grupos'],
        request=AssignStudentSerializer,
        responses={200: OpenApiResponse(description='Alumno asignado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def post(self, request, pk):
        try:
            group = Group.objects.select_related('id_period').get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not group.status:
            return error_response(
                'No se puede asignar alumnos a un grupo inactivo.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssignStudentSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Asignación de alumno rechazada | group_id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)

        id_person = serializer.validated_data['id_person']
        try:
            student = StudentProfile.objects.select_related('user').get(pk=id_person)
        except StudentProfile.DoesNotExist:
            return error_response('El alumno especificado no existe.', status_code=status.HTTP_404_NOT_FOUND)

        try:
            student.group = group
            student.save(update_fields=['group_id'])
            logger.info('Alumno asignado a grupo | person_id={} group_id={}', id_person, pk)
        except IntegrityError as exc:
            logger.error('IntegrityError al asignar alumno | person_id={} group_id={} detail={}', id_person, pk, exc)
            return error_response(
                'No se pudo asignar el alumno al grupo por conflicto de integridad.',
                status_code=status.HTTP_409_CONFLICT,
            )

        return success_response(
            {'id_person': student.pk, 'id_group': group.pk},
            'Alumno asignado al grupo exitosamente.',
        )


# ---------------------------------------------------------------------------
# Subject views  (MAT-001 → MAT-003)
# ---------------------------------------------------------------------------

class SubjectListCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar materias',
        tags=['Materias'],
        parameters=[
            OpenApiParameter('academic_level', OpenApiTypes.INT, description='Filter by academic level', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: SubjectSerializer(many=True)},
    )
    def get(self, request):
        queryset = Subject.objects.prefetch_related('units').all()
        academic_level = request.query_params.get('academic_level')
        status_param = request.query_params.get('status')
        if academic_level:
            queryset = queryset.filter(level_number=academic_level)
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))
        logger.info('Materias consultadas | count={}', queryset.count())
        return paginated_success_response(request, queryset, SubjectSerializer)

    @extend_schema(
        summary='Registrar materia',
        tags=['Materias'],
        request=SubjectSerializer,
        responses={201: SubjectSerializer},
    )
    def post(self, request):
        serializer = SubjectSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Registro de materia rechazado | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            number_of_units = serializer.validated_data.pop('number_of_units', 0)
            instance = serializer.save()
            
            # Auto-create Units if number_of_units is provided
            if number_of_units > 0:
                units_created = []
                for i in range(1, number_of_units + 1):
                    unit = Unit.objects.create(
                        id_subject=instance,
                        unit_name=f'Unidad {i}',
                        unit_number=i,
                    )
                    units_created.append(unit.pk)
                logger.info(
                    'Materia registrada con unidades | id={} name={} level={} units={}',
                    instance.pk, instance.name, instance.level_number, units_created
                )
            else:
                logger.info(
                    'Materia registrada | id={} name={} level={}',
                    instance.pk, instance.name, instance.level_number
                )
        except IntegrityError as exc:
            logger.error('IntegrityError al registrar materia | detail={}', exc)
            return error_response(
                'No se pudo registrar la materia por conflicto de integridad.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Materia registrada exitosamente.', status.HTTP_201_CREATED)


class SubjectDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def _get_subject(self, pk):
        try:
            return Subject.objects.prefetch_related('units').get(pk=pk)
        except Subject.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener materia',
        tags=['Materias'],
        responses={200: SubjectSerializer, 404: OpenApiResponse(description='No encontrada')},
    )
    def get(self, request, pk):
        subject = self._get_subject(pk)
        if not subject:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        return success_response(SubjectSerializer(subject).data)

    @extend_schema(
        summary='Actualizar materia',
        tags=['Materias'],
        request=SubjectSerializer,
        responses={200: SubjectSerializer, 404: OpenApiResponse(description='No encontrada')},
    )
    def put(self, request, pk):
        subject = self._get_subject(pk)
        if not subject:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = SubjectSerializer(subject, data=request.data)
        if not serializer.is_valid():
            logger.warning('Actualización de materia rechazada | id={} errors={}', pk, serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            serializer.save()
            logger.info('Materia actualizada | id={}', pk)
        except IntegrityError as exc:
            logger.error('IntegrityError al actualizar materia | id={} detail={}', pk, exc)
            return error_response(
                'No se pudo actualizar la materia por conflicto de integridad.',
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(serializer.data, 'Materia actualizada exitosamente.')


class SubjectUnitsBySubjectView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar unidades por materia',
        tags=['Materias'],
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: UnitSerializer(many=True), 404: OpenApiResponse(description='Materia no encontrada')},
    )
    def get(self, request, pk):
        try:
            subject = Subject.objects.get(pk=pk)
        except Subject.DoesNotExist:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        units = Unit.objects.filter(id_subject=subject).order_by('unit_number', 'id_unit')
        return paginated_success_response(request, units, UnitSerializer)

class SubjectStatusView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Cambiar estado de materia',
        tags=['Materias'],
        request=StatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrada')},
    )
    def patch(self, request, pk):
        try:
            subject = Subject.objects.get(pk=pk)
        except Subject.DoesNotExist:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        subject.status = serializer.validated_data['status']
        subject.save(update_fields=['status'])
        state = 'activada' if subject.status else 'desactivada'
        logger.info('Materia {} | id={}', state, pk)
        return success_response(
            {'id_subject': subject.pk, 'status': subject.status},
            f'Materia {state} exitosamente.',
        )
