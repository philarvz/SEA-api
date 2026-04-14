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
from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import Generation, Period, Group, Subject, Unit, GroupTeacherAssignment
from rest_framework.throttling import UserRateThrottle

from .serializers import (
    GenerationSerializer,
    PeriodSerializer,
    GroupSerializer,
    GroupCreateSerializer,
    GroupUpdateSerializer,
    SubjectSerializer,
    UnitSerializer,
    GroupStatusUpdateSerializer,
    AssignStudentSerializer,
    CreateGroupTeacherAssignmentSerializer,
    AvailableTeacherSerializer,
    TeacherSubjectSerializer,
    AssignableGroupSerializer,
    AssignableGroupWithSubjectSerializer,
)
from .permissions import IsTeacherOrAdmin
from .services import PeriodService
from apps.users.models import StudentProfile, TeacherProfile
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
        request=GroupStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrada')},
    )
    def patch(self, request, pk):
        try:
            generation = Generation.objects.get(pk=pk)
        except Generation.DoesNotExist:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GroupStatusUpdateSerializer(data=request.data)
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
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: PeriodSerializer(many=True)},
    )
    def get(self, request):
        queryset = Period.objects.all()
        status_param = request.query_params.get('status')
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))
        logger.info('Periodos consultados | count={}', queryset.count())
        return paginated_success_response(request, queryset, PeriodSerializer)

    @extend_schema(
        summary='Registrar periodo académico (solo nombre)',
        tags=['Periodos'],
        request=PeriodSerializer,
        responses={201: PeriodSerializer},
    )
    def post(self, request):
        # Only accept period_name; dates are auto-calculated from current year
        serializer = PeriodSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Registro de periodo rechazado | errors={}', serializer.errors)
            return error_response(MSG_INVALID_DATA, serializer.errors)
        try:
            instance = serializer.save()
            logger.info('Periodo registrado | id={} name={}', instance.pk, instance.period_name)
        except IntegrityError as exc:
            logger.error('IntegrityError al registrar periodo | detail={}', exc)
            return error_response(
                'Ya existe un periodo con ese nombre.',
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
        summary='Actualizar periodo académico (solo año y nombre)',
        tags=['Periodos'],
        request=PeriodSerializer,
        responses={200: PeriodSerializer, 404: OpenApiResponse(description='No encontrado')},
    )
    def put(self, request, pk):
        period = self._get_period(pk)
        if not period:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        # Only accept year and period_name; dates are auto-calculated
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
        request=GroupStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def patch(self, request, pk):
        try:
            period = Period.objects.get(pk=pk)
        except Period.DoesNotExist:
            return error_response(MSG_PERIOD_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GroupStatusUpdateSerializer(data=request.data)
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
            OpenApiParameter('group_letter', OpenApiTypes.STR, description='Buscar por letra de grupo', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: GroupSerializer(many=True)},
    )
    def get(self, request):
        queryset = (
            Group.objects
            .select_related('id_generation')
            .prefetch_related('teacher_assignments__teacher__user', 'teacher_assignments__subject')
            .annotate(students_count=Count('students'))
            .order_by('id_generation', 'group_letter')
        )
        id_generation = request.query_params.get('id_generation')
        academic_level = request.query_params.get('academic_level')
        group_letter = request.query_params.get('group_letter')
        status_param = request.query_params.get('status')
        if id_generation:
            queryset = queryset.filter(id_generation_id=id_generation)
        if academic_level:
            queryset = queryset.filter(academic_level=academic_level)
        if group_letter:
            queryset = queryset.filter(group_letter__icontains=group_letter)
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

        try:
            generation = Generation.objects.get(pk=data['id_generation'])
        except Generation.DoesNotExist:
            return error_response(MSG_GENERATION_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        resolved_level = PeriodService.calculate_generation_academic_level(
            generation_year=generation.year,
            total_levels=generation.total_levels,
        )

        try:
            group = Group.objects.create(
                id_generation=generation,
                group_letter=data['group_letter'],
                academic_level=resolved_level,
                status=data.get('status', True),
            )
            logger.info(
                'Group created | id={} letter={} academic_level={}',
                group.pk, group.group_letter, group.academic_level,
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
            return Group.objects.select_related('id_generation').prefetch_related(
                'teacher_assignments__teacher__user', 'teacher_assignments__subject'
            ).get(pk=pk)
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
        resolved_level = PeriodService.calculate_generation_academic_level(
            generation_year=group.id_generation.year,
            total_levels=group.id_generation.total_levels,
        )
        try:
            group.group_letter = data['group_letter']
            group.academic_level = resolved_level
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
        request=GroupStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrado')},
    )
    def patch(self, request, pk):
        try:
            group = Group.objects.get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GroupStatusUpdateSerializer(data=request.data)
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
            group = Group.objects.get(pk=pk)
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
# Group ↔ Teacher assignments  (M:N via GroupTeacherAssignment)
# ---------------------------------------------------------------------------

class GroupAssignmentsView(APIView):
    """
    GET  /api/academic/groups/{pk}/assignments/  — list all subject-teacher assignments
    POST /api/academic/groups/{pk}/assignments/  — create one assignment
        Body: { teacher_id: int, subject_id: int }
    Business rules for POST:
      - Group must be active.
      - Subject must belong to this group's current academic_level.
      - Teacher must be active, have role=teacher, and have that subject assigned.
      - Replaces existing assignment for the same subject (upsert behaviour).
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar asignaciones docente-materia de un grupo',
        tags=['Grupos'],
        responses={200: OpenApiResponse(description='Lista de asignaciones')},
    )
    def get(self, request, pk):
        try:
            Group.objects.get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        assignments = (
            GroupTeacherAssignment.objects
            .filter(group=group)
            .select_related('teacher__user', 'subject')
        )
        data = [
            {
                'id_assignment': a.pk,
                'subject': {'id_subject': a.subject.pk, 'name': a.subject.name},
                'teacher': {
                    'id_teacher': a.teacher.pk,
                    'full_name': a.teacher.user.full_name,
                    'email': a.teacher.user.email,
                },
            }
            for a in assignments
        ]
        return success_response({'results': data})

    @extend_schema(
        summary='Asignar docente a una materia del grupo',
        tags=['Grupos'],
        request=CreateGroupTeacherAssignmentSerializer,
        responses={
            200: OpenApiResponse(description='Asignación creada o actualizada'),
            400: OpenApiResponse(description='Error de validación de negocio'),
            404: OpenApiResponse(description='No encontrado'),
        },
    )
    def post(self, request, pk):
        try:
            group = Group.objects.select_related('id_generation').get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if not group.status:
            return error_response('No se puede asignar docentes a un grupo inactivo.', status_code=status.HTTP_400_BAD_REQUEST)

        serializer = CreateGroupTeacherAssignmentSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Datos inválidos.', serializer.errors)

        teacher_id = serializer.validated_data['teacher_id']
        subject_id = serializer.validated_data['subject_id']

        # Validate subject exists and belongs to group's level
        try:
            subject = Subject.objects.get(pk=subject_id, status=True)
        except Subject.DoesNotExist:
            return error_response('La materia especificada no existe o está inactiva.', status_code=status.HTTP_404_NOT_FOUND)

        current_level = PeriodService.sync_group_academic_level(group)
        if subject.level_number != current_level:
            return error_response(
                f'La materia "{subject.name}" pertenece al nivel {subject.level_number}, '
                f'pero este grupo está en el nivel {current_level}.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate teacher
        try:
            teacher = TeacherProfile.objects.select_related('user').prefetch_related('subjects').get(pk=teacher_id)
        except TeacherProfile.DoesNotExist:
            return error_response('El docente especificado no existe.', status_code=status.HTTP_404_NOT_FOUND)

        if not teacher.user.is_active or teacher.user.role != 'teacher':
            return error_response('El docente no está activo o no tiene el rol correcto.', status_code=status.HTTP_400_BAD_REQUEST)

        if not teacher.subjects.filter(pk=subject_id, status=True).exists():
            return error_response(
                f'El docente no imparte la materia "{subject.name}".',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Upsert: replace existing assignment for this subject in this group
        assignment, created = GroupTeacherAssignment.objects.update_or_create(
            group=group,
            subject=subject,
            defaults={'teacher': teacher},
        )
        action = 'creada' if created else 'actualizada'
        logger.info('Asignación {} | group_id={} subject_id={} teacher_id={}', action, pk, subject_id, teacher_id)
        return success_response(
            {
                'id_assignment': assignment.pk,
                'subject': {'id_subject': subject.pk, 'name': subject.name},
                'teacher': {
                    'id_teacher': teacher.pk,
                    'full_name': teacher.user.full_name,
                    'email': teacher.user.email,
                },
            },
            f'Asignación {action} exitosamente.',
        )


class GroupAssignmentDetailView(APIView):
    """
    DELETE /api/academic/groups/{pk}/assignments/{a_pk}/
    Removes a specific teacher-subject assignment from a group.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Eliminar asignación docente-materia de un grupo',
        tags=['Grupos'],
        responses={200: OpenApiResponse(description='Asignación eliminada'), 404: OpenApiResponse(description='No encontrada')},
    )
    def delete(self, request, pk, a_pk):
        try:
            assignment = GroupTeacherAssignment.objects.select_related(
                'group', 'subject', 'teacher__user'
            ).get(pk=a_pk, group_id=pk)
        except GroupTeacherAssignment.DoesNotExist:
            return error_response('Asignación no encontrada.', status_code=status.HTTP_404_NOT_FOUND)

        assignment.delete()
        logger.info('Asignación eliminada | group_id={} assignment_id={}', pk, a_pk)
        return success_response({'id_assignment': a_pk}, 'Asignación eliminada exitosamente.')


class GroupAvailableTeachersView(APIView):
    """
    GET /api/academic/groups/{pk}/available-teachers/?subject_id=X
    Returns teachers eligible to teach a specific subject in this group.
    subject_id is required. The subject must match the group's current academic_level.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Listar docentes disponibles para una materia en un grupo',
        tags=['Grupos'],
        parameters=[OpenApiParameter('subject_id', OpenApiTypes.INT, description='ID de materia requerido', required=True)],
        responses={200: AvailableTeacherSerializer(many=True), 400: OpenApiResponse(description='subject_id requerido'), 404: OpenApiResponse(description='No encontrado')},
    )
    def get(self, request, pk):
        try:
            group = Group.objects.select_related('id_generation').get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        subject_id = request.query_params.get('subject_id')
        if not subject_id:
            return error_response('El parámetro subject_id es requerido.', status_code=status.HTTP_400_BAD_REQUEST)

        try:
            subject = Subject.objects.get(pk=subject_id, status=True)
        except Subject.DoesNotExist:
            return error_response('La materia especificada no existe.', status_code=status.HTTP_404_NOT_FOUND)

        current_level = PeriodService.sync_group_academic_level(group)
        if subject.level_number != current_level:
            return error_response(
                f'La materia "{subject.name}" no corresponde al nivel {current_level} del grupo.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        eligible_teachers = (
            TeacherProfile.objects
            .filter(
                user__is_active=True,
                user__role='teacher',
                subjects__pk=subject_id,
                subjects__status=True,
            )
            .distinct()
            .select_related('user')
        )

        results = [
            {
                'id_teacher': tp.pk,
                'full_name': tp.user.full_name,
                'email': tp.user.email,
            }
            for tp in eligible_teachers
        ]
        logger.info('Docentes disponibles para materia | group_id={} subject_id={} count={}', pk, subject_id, len(results))
        return success_response({'results': results})


class GroupStudentsView(APIView):
    """
    GET /api/academic/groups/{pk}/students/
    Returns a paginated list of students in a group.
    - Admin: unrestricted.
    - Teacher: only groups they are assigned to (via GroupTeacherAssignment).
    Response fields: id_user, full_name, matricula, email.
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Alumnos de un grupo',
        tags=['Grupos'],
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, description='N\u00famero de p\u00e1gina', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por p\u00e1gina', required=False),
        ],
        responses={200: OpenApiResponse(description='Lista paginada de alumnos')},
    )
    def get(self, request, pk):
        try:
            Group.objects.get(pk=pk)
        except Group.DoesNotExist:
            return error_response(MSG_GROUP_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        # Teachers can only see students from groups they are assigned to
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')
        if role == 'teacher':
            assigned = GroupTeacherAssignment.objects.filter(
                group_id=pk,
                teacher__user_id=request.user.id,
            ).exists()
            if not assigned:
                return error_response(
                    'No tienes acceso a los alumnos de este grupo.',
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        students_qs = (
            StudentProfile.objects
            .filter(group_id=pk)
            .select_related('user')
            .order_by('user__last_name', 'user__first_name')
        )

        paginator = CatalogPagination()
        page = paginator.paginate_queryset(students_qs, request)
        page_size = paginator.get_page_size(request) or paginator.page_size

        results = [
            {
                'id_user': sp.user.pk,
                'full_name': sp.user.full_name,
                'matricula': sp.user.matricula or '',
                'email': sp.user.email,
            }
            for sp in page
        ]

        payload = {
            'results': results,
            'pagination': {
                'count': paginator.page.paginator.count,
                'page': paginator.page.number,
                'page_size': page_size,
                'total_pages': paginator.page.paginator.num_pages,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
        }
        logger.info('Alumnos de grupo | group_id={} count={}', pk, paginator.page.paginator.count)
        return success_response(payload)


class _TeacherMyGroupsThrottle(UserRateThrottle):
    """Dedicated throttle scope for teacher/admin group-selector listing."""
    scope = 'teacher_my_groups'


class TeacherMyGroupsView(APIView):
    """
    GET /api/academic/groups/my-groups/
    Returns the groups accessible to the authenticated user without pagination,
    intended for use in dropdown / selector widgets:
    - Teacher: returns only groups where the teacher has a GroupTeacherAssignment.
    - Admin: returns all active groups.
    Ownership is enforced for teachers: the query filters through the
    authenticated user's TeacherProfile, so a teacher can never see groups
    outside their own assignments.
    """
    permission_classes = [IsTeacherOrAdmin]
    throttle_classes = [_TeacherMyGroupsThrottle]

    @extend_schema(
        summary='Grupos accesibles para asignación de examen',
        tags=['Grupos'],
        parameters=[
            OpenApiParameter(
                name='exam_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    'ID del examen. Si se provée, filtra grupos por la materia del examen. '
                    'El docente sólo puede consultar examen own. '
                    'Admin ve todos los grupos activos del nivel de la materia.'
                ),
            )
        ],
        responses={200: AssignableGroupWithSubjectSerializer(many=True)},
    )
    def _resolve_subject_from_exam(self, exam_id_raw, role, user):
        """
        Validates exam_id query param and returns (subject, error_response).
        Returns (None, None) when exam_id is not provided.
        Returns (None, Response) on validation or authorisation failure.
        """
        from apps.exams.models import Exam  # lazy import avoids circular dependency

        if exam_id_raw is None:
            return None, None
        try:
            exam_id_int = int(exam_id_raw)
            if exam_id_int <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return None, error_response('Parámetro exam_id inválido.')
        try:
            exam = Exam.objects.select_related('id_subject').get(pk=exam_id_int)
        except Exam.DoesNotExist:
            return None, error_response(
                'Examen no encontrado.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if role != 'admin' and exam.id_teacher_id != user.pk:
            return None, error_response(
                'No autorizado para consultar los grupos de este examen.',
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return exam.id_subject, None

    def get(self, request):
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')

        subject, err = self._resolve_subject_from_exam(
            request.query_params.get('exam_id'), role, request.user,
        )
        if err is not None:
            return err

        serializer_context = {'subject_name': subject.name if subject is not None else None}

        if role == 'admin':
            base_qs = (
                Group.objects
                .select_related('id_generation')
                .filter(status=True)
            )
            if subject is not None:
                base_qs = base_qs.filter(academic_level=subject.level_number)
            queryset = base_qs.order_by('academic_level', 'group_letter')
            serializer = AssignableGroupWithSubjectSerializer(
                queryset, many=True, context=serializer_context,
            )
            logger.info(
                'All groups listed for exam assignment selector | user={} count={}',
                request.user.pk, len(serializer.data),
            )
            return success_response(serializer.data)

        # Teacher path — ownership implicitly enforced via user.pk
        try:
            profile = TeacherProfile.objects.get(user_id=request.user.pk)
        except TeacherProfile.DoesNotExist:
            logger.info(
                'Teacher my-groups requested but no profile found | user={}',
                request.user.pk,
            )
            return success_response([])

        assignment_filter: dict = {'teacher': profile}
        if subject is not None:
            assignment_filter['subject'] = subject

        group_ids = (
            GroupTeacherAssignment.objects
            .filter(**assignment_filter)
            .values_list('group_id', flat=True)
            .distinct()
        )
        queryset = (
            Group.objects
            .select_related('id_generation')
            .filter(pk__in=group_ids, status=True)
            .order_by('academic_level', 'group_letter')
        )
        serializer = AssignableGroupWithSubjectSerializer(
            queryset, many=True, context=serializer_context,
        )
        logger.info(
            'Teacher my-groups listed for exam assignment selector | user={} count={}',
            request.user.pk, len(serializer.data),
        )
        return success_response(serializer.data)


# ---------------------------------------------------------------------------
# Teacher: groups by subject  (TC-002)
# ---------------------------------------------------------------------------

class TeacherSubjectsWithGroupsView(APIView):
    """
    GET /api/academic/subjects/my-subjects-with-groups/
    Returns a plain list of subject IDs for which the authenticated teacher
    has at least one GroupTeacherAssignment (i.e. is assigned to at least one group).
    Admin: returns all subject IDs that appear in any assignment.
    Used by the frontend to determine which subject cards should show
    a "Ver grupos" button vs "Sin grupos asignados".
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='IDs de materias del docente que tienen grupos asignados',
        tags=['Materias'],
        responses={200: OpenApiResponse(description='Lista de IDs de materias con grupos')},
    )
    def get(self, request):
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')

        if role == 'admin':
            subject_ids = list(
                GroupTeacherAssignment.objects
                .values_list('subject_id', flat=True)
                .distinct()
            )
            logger.info('Admin: subjects with group assignments | count={}', len(subject_ids))
            return success_response(subject_ids)

        try:
            profile = TeacherProfile.objects.get(user_id=request.user.pk)
        except TeacherProfile.DoesNotExist:
            logger.info('TeacherSubjectsWithGroups: no profile | user={}', request.user.pk)
            return success_response([])

        subject_ids = list(
            GroupTeacherAssignment.objects
            .filter(teacher=profile)
            .values_list('subject_id', flat=True)
            .distinct()
        )
        logger.info('Teacher subjects with groups | user={} count={}', request.user.pk, len(subject_ids))
        return success_response(subject_ids)


class SubjectTeacherGroupsView(APIView):
    """
    GET /api/academic/subjects/<pk>/my-groups/
    Returns groups where the authenticated teacher has a GroupTeacherAssignment
    for the given subject (i.e. the groups where they teach that subject).
    Admin: returns all active groups with an assignment for that subject.
    Each group includes students_count so the card can display it directly.
    Response: { results: [ ...groups... ] }
    """
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        summary='Grupos del docente para una materia concreta',
        tags=['Materias'],
        responses={200: AssignableGroupSerializer(many=True)},
    )
    def get(self, request, pk):
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')

        try:
            subject = Subject.objects.get(pk=pk)
        except Subject.DoesNotExist:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if role == 'admin':
            group_ids = (
                GroupTeacherAssignment.objects
                .filter(subject=subject)
                .values_list('group_id', flat=True)
                .distinct()
            )
        else:
            try:
                profile = TeacherProfile.objects.get(user_id=request.user.pk)
            except TeacherProfile.DoesNotExist:
                return success_response({'results': []})

            group_ids = (
                GroupTeacherAssignment.objects
                .filter(teacher=profile, subject=subject)
                .values_list('group_id', flat=True)
                .distinct()
            )

        queryset = (
            Group.objects
            .select_related('id_generation')
            .annotate(students_count=Count('students'))
            .filter(pk__in=group_ids, status=True)
            .order_by('academic_level', 'group_letter')
        )
        serializer = AssignableGroupSerializer(queryset, many=True)
        logger.info(
            'Subject teacher groups | subject_id={} user={} count={}',
            pk, request.user.pk, len(serializer.data),
        )
        return success_response({'results': serializer.data})


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
            OpenApiParameter('name', OpenApiTypes.STR, description='Buscar por nombre de materia', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={200: SubjectSerializer(many=True)},
    )
    def get(self, request):
        queryset = Subject.objects.prefetch_related('units').all()
        academic_level = request.query_params.get('academic_level')
        name = request.query_params.get('name')
        status_param = request.query_params.get('status')
        if academic_level:
            queryset = queryset.filter(level_number=academic_level)
        if name:
            queryset = queryset.filter(name__icontains=name)
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
        request=GroupStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Estado actualizado'), 404: OpenApiResponse(description='No encontrada')},
    )
    def patch(self, request, pk):
        try:
            subject = Subject.objects.get(pk=pk)
        except Subject.DoesNotExist:
            return error_response(MSG_SUBJECT_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
        serializer = GroupStatusUpdateSerializer(data=request.data)
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


# ---------------------------------------------------------------------------
# Teacher: my assigned subjects  (TC-001)
# ---------------------------------------------------------------------------

class _TeacherSubjectsThrottle(UserRateThrottle):
    """Dedicated throttle scope for teacher subject listing."""
    scope = 'teacher_subjects'


class TeacherSubjectsView(APIView):
    """
    GET /api/academic/subjects/my-subjects/
    - Teacher: returns only the subjects assigned to the authenticated teacher.
    - Admin: returns all subjects in the system (full catalogue access).
    Ownership is enforced implicitly for teachers: the query always uses
    request.user.pk, so a teacher can never access another teacher's subjects.
    Supports pagination and search by name.
    """
    permission_classes = [IsTeacherOrAdmin]
    throttle_classes = [_TeacherSubjectsThrottle]

    @extend_schema(
        summary='Materias del docente autenticado (o todas, si es administrador)',
        tags=['Materias'],
        parameters=[
            OpenApiParameter('name', OpenApiTypes.STR, description='Buscar por nombre de materia', required=False),
            OpenApiParameter('status', OpenApiTypes.BOOL, description='Filtrar por estado activo', required=False),
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Elementos por página', required=False),
        ],
        responses={
            200: TeacherSubjectSerializer(many=True),
        },
    )
    def get(self, request):
        role = getattr(request.user, 'role', None)
        if role is None and request.auth is not None:
            role = request.auth.get('role')

        name_filter = request.query_params.get('name')
        status_param = request.query_params.get('status')

        def _apply_status_filter(qs):
            if status_param is None:
                return qs
            active = str(status_param).lower() in ('true', '1')
            return qs.filter(status=active)

        if role == 'admin':
            subjects = (
                Subject.objects.prefetch_related('units')
                .order_by('level_number', 'name')
            )
            if name_filter:
                subjects = subjects.filter(name__icontains=name_filter)
            subjects = _apply_status_filter(subjects)

            logger.info(
                'All subjects listed by admin | user={} count={}',
                request.user.pk, subjects.count(),
            )
            return paginated_success_response(request, subjects, TeacherSubjectSerializer)

        # Teacher path — ownership implicitly enforced via user.pk
        try:
            profile = TeacherProfile.objects.prefetch_related(
                'subjects__units'
            ).get(user_id=request.user.pk)
        except TeacherProfile.DoesNotExist:
            logger.info('Teacher subjects requested but no profile found | user={}', request.user.pk)
            return success_response({'results': []})

        subjects = (
            profile.subjects
            .prefetch_related('units')
            .order_by('level_number', 'name')
        )
        if name_filter:
            subjects = subjects.filter(name__icontains=name_filter)
        subjects = _apply_status_filter(subjects)

        logger.info(
            'Teacher subjects listed | user={} count={}',
            request.user.pk, subjects.count(),
        )
        return paginated_success_response(request, subjects, TeacherSubjectSerializer)
