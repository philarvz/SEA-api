from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django.contrib.auth import get_user_model
from django.db import models

from .permissions import IsAdmin

# Constantes para mensajes de error
MSG_USER_NOT_FOUND = 'Usuario no encontrado.'
MSG_INVALID_DATA = 'Datos inválidos.'
from .serializers import (
    RegisterUserSerializer, 
    UserResponseSerializer, 
    UserListSerializer, 
    UpdateUserSerializer,
    StatusUpdateSerializer,
    RequestPasswordResetSerializer,
    VerifyResetCodeSerializer,
    ResetPasswordSerializer,
)
from .services import UserRegistrationService, UserUpdateService, PasswordRecoveryService
from utils.responses import success_response, error_response
from utils.pagination import GlobalPagination

User = get_user_model()


class UserListCreateView(APIView):
    """
    Vista para listar y crear usuarios.
    Endpoints:
        GET /api/users/ - Listar usuarios con paginación y filtros
        POST /api/users/ - Crear nuevo usuario
    """

    permission_classes = [IsAdmin]

    @extend_schema(
        summary='Listar todos los usuarios',
        tags=['Usuarios'],
        parameters=[
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Número de página',
                required=False,
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Registros por página (max: 100)',
                required=False,
            ),
            OpenApiParameter(
                name='role',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar por rol (student, teacher, admin)',
                required=False,
                enum=['student', 'teacher', 'admin'],
            ),
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filtrar por estado (true/false)',
                required=False,
                enum=['true', 'false'],
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Buscar por nombre, apellido, matrícula o email',
                required=False,
            ),
            OpenApiParameter(
                name='group',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filtrar estudiantes por ID de grupo (solo aplica cuando role=student)',
                required=False,
            ),
        ],
        responses={
            200: UserListSerializer(many=True),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Obtiene un listado paginado de todos los usuarios del sistema. '
            'Solo los administradores pueden acceder. '
            'Soporta filtros por rol, estado, grupo (para estudiantes) y búsqueda por texto.'
        ),
    )
    def get(self, request):
        try:
            logger.info(
                'Listing users | requester={} page={} page_size={}',
                request.user.username,
                request.query_params.get('page', 1),
                request.query_params.get('page_size', 10),
            )
            
            # Construir queryset con filtros
            queryset = self._get_filtered_queryset(request)
            
            # Aplicar paginación
            paginator = GlobalPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            
            # Serializar datos
            serializer = UserListSerializer(paginated_queryset, many=True)
            
            # Retornar respuesta paginada
            return paginator.get_paginated_response(serializer.data)
            
        except Exception as exc:
            logger.error('Error listing users | {}', exc)
            return error_response(
                'Error al obtener el listado de usuarios.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary='Registrar nuevo usuario',
        tags=['Usuarios'],
        request=RegisterUserSerializer,
        responses={
            201: UserResponseSerializer,
            400: OpenApiResponse(description='Datos de entrada inválidos'),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Crea un nuevo usuario (alumno, docente o administrador). '
            'Solo los administradores pueden acceder. '
            'La clave se genera automáticamente y se envía al correo del usuario.'
        ),
    )
    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                'User registration rejected | errors={}', serializer.errors
            )
            return error_response(MSG_INVALID_DATA, serializer.errors)

        try:
            user, _ = UserRegistrationService.register_user(serializer.validated_data)
            return success_response(
                UserResponseSerializer(user).data,
                'Usuario registrado exitosamente. Se ha enviado un correo con las credenciales.',
                status.HTTP_201_CREATED,
            )
        except Exception as exc:
            logger.error('Error registering user | {}', exc)
            return error_response(
                'Error interno al registrar el usuario.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_filtered_queryset(self, request):
        """
        Retorna el queryset de usuarios con filtros aplicados.
        Aplica select_related y prefetch_related para optimizar consultas.
        """
        queryset = User.objects.select_related(
            'student_profile',
            'student_profile__group',
            'teacher_profile',
        ).prefetch_related(
            'teacher_profile__subjects'
        ).order_by('-date_joined')

        # Filtro por rol
        role = request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
            logger.debug('Filtering by role | role={}', role)

        # Filtro por estado
        status_param = request.query_params.get('status', None)
        if status_param is not None:
            status_bool = status_param.lower() == 'true'
            queryset = queryset.filter(status=status_bool)
            logger.debug('Filtering by status | status={}', status_bool)

<<<<<<< HEAD
        # Filtro por grupo (solo para estudiantes)
        group = request.query_params.get('group', None)
        if group:
            try:
                group_id = int(group)
                queryset = queryset.filter(
                    role='student',
                    student_profile__group_id=group_id
                )
                logger.debug('Filtering by group | group_id={}', group_id)
            except ValueError:
                logger.warning('Invalid group parameter | group={}', group)
=======
        # Filtro por grupo (para listar alumnos de un grupo específico)
        group_id = request.query_params.get('group_id', None)
        if group_id:
            queryset = queryset.filter(student_profile__group_id=group_id)
            logger.debug('Filtering by group_id | group_id={}', group_id)
>>>>>>> develop

        # Búsqueda por texto
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(matricula__icontains=search) |
                models.Q(email__icontains=search)
            )
            logger.debug('Searching users | query={}', search)

        total_count = queryset.count()
        logger.info('Users queryset built | total_count={}', total_count)

        return queryset


class UserDetailView(APIView):
    """
    Vista para obtener y actualizar un usuario específico.
    Endpoints:
        GET /api/users/{id}/ - Obtener detalle de usuario
        PUT /api/users/{id}/ - Actualizar usuario
    """

    permission_classes = [IsAdmin]

    def _get_user(self, pk):
        """Helper para obtener el usuario o retornar None si no existe."""
        try:
            return User.objects.select_related(
                'student_profile',
                'student_profile__group',
                'teacher_profile',
            ).prefetch_related(
                'teacher_profile__subjects'
            ).get(pk=pk)
        except User.DoesNotExist:
            return None

    @extend_schema(
        summary='Obtener usuario',
        tags=['Usuarios'],
        responses={
            200: UserResponseSerializer,
            404: OpenApiResponse(description='Usuario no encontrado'),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
        },
        description='Obtiene los detalles completos de un usuario específico.',
    )
    def get(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return error_response(
                MSG_USER_NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UserResponseSerializer(user)
        return success_response(serializer.data)

    @extend_schema(
        summary='Actualizar usuario',
        tags=['Usuarios'],
        request=UpdateUserSerializer,
        responses={
            200: UserResponseSerializer,
            400: OpenApiResponse(description='Datos de entrada inválidos'),
            404: OpenApiResponse(description='Usuario no encontrado'),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Actualiza la información de un usuario existente. '
            'Permite actualizar datos básicos, rol y datos específicos del rol '
            '(grupo para estudiantes, materias para docentes).'
        ),
    )
    def put(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return error_response(
                MSG_USER_NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UpdateUserSerializer(
            data=request.data,
            context={'user_id': pk}
        )
        
        if not serializer.is_valid():
            logger.warning(
                'User update rejected | user_id={} errors={}',
                pk, serializer.errors
            )
            return error_response(MSG_INVALID_DATA, serializer.errors)
        
        try:
            updated_user = UserUpdateService.update_user(user, serializer.validated_data)
            return success_response(
                UserResponseSerializer(updated_user).data,
                'Usuario actualizado exitosamente.',
            )
        except Exception as exc:
            logger.error('Error updating user | user_id={} error={}', pk, exc)
            return error_response(
                'Error interno al actualizar el usuario.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserStatusView(APIView):
    """
    Vista para cambiar el estado de un usuario (activo/inactivo).
    Endpoint: PATCH /api/users/{id}/status/
    """

    permission_classes = [IsAdmin]

    @extend_schema(
        summary='Cambiar estado de usuario',
        tags=['Usuarios'],
        request=StatusUpdateSerializer,
        responses={
            200: OpenApiResponse(description='Estado actualizado exitosamente'),
            404: OpenApiResponse(description='Usuario no encontrado'),
            400: OpenApiResponse(description='Datos inválidos'),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
        },
        description=(
            'Cambia el estado de un usuario entre activo (true) e inactivo (false). '
            'Solo los administradores pueden acceder.'
        ),
    )
    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return error_response(
                MSG_USER_NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = StatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        
        new_status = serializer.validated_data['status']
        user.status = new_status
        user.is_active = new_status
        user.save(update_fields=['status', 'is_active'])
        
        state = 'activado' if new_status else 'desactivado'
        logger.info('User status changed | user_id={} new_status={}', pk, new_status)
        
        return success_response(
            {
                'id_user': user.pk,
                'status': user.status,
                'is_active': user.is_active
            },
            f'Usuario {state} exitosamente.',
        )


# ---------------------------------------------------------------------------
# Password Recovery Views
# ---------------------------------------------------------------------------

class RequestPasswordResetView(APIView):
    """
    Solicitar código de verificación para recuperación de contraseña
    Endpoint: POST /api/users/password-recovery/request/
    """
    
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Solicitar código de recuperación de contraseña',
        tags=['Recuperación de Contraseña'],
        request=RequestPasswordResetSerializer,
        responses={
            200: OpenApiResponse(description='Código enviado exitosamente'),
            400: OpenApiResponse(description='Datos inválidos'),
            500: OpenApiResponse(description='Error al enviar el correo'),
        },
        description=(
            'Envía un código de verificación de 6 dígitos al correo electrónico proporcionado. '
            'El código expira en 15 minutos.'
        ),
    )
    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        
        try:
            result = PasswordRecoveryService.request_password_reset(
                email=serializer.validated_data['email']
            )
            return success_response(result, result['message'])
        except Exception as e:
            logger.error(f'Error in password reset request: {e}')
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyResetCodeView(APIView):
    """
    Verificar código de recuperación de contraseña
    Endpoint: POST /api/users/password-recovery/verify/
    """
    
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Verificar código de recuperación',
        tags=['Recuperación de Contraseña'],
        request=VerifyResetCodeSerializer,
        responses={
            200: OpenApiResponse(description='Código válido'),
            400: OpenApiResponse(description='Código inválido o expirado'),
        },
        description=(
            'Verifica si el código de 6 dígitos es válido y no ha expirado.'
        ),
    )
    def post(self, request):
        serializer = VerifyResetCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        
        try:
            result = PasswordRecoveryService.verify_reset_code(
                email=serializer.validated_data['email'],
                code=serializer.validated_data['code']
            )
            return success_response(result, result['message'])
        except ValueError as e:
            return error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error verifying reset code: {e}')
            return error_response(
                'Error al verificar el código.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPasswordView(APIView):
    """
    Restablecer contraseña con código verificado
    Endpoint: POST /api/users/password-recovery/reset/
    """
    
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Restablecer contraseña',
        tags=['Recuperación de Contraseña'],
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description='Contraseña restablecida exitosamente'),
            400: OpenApiResponse(description='Datos inválidos o código expirado'),
        },
        description=(
            'Restablece la contraseña del usuario después de verificar el código. '
            'El código se marca como usado y no puede reutilizarse.'
        ),
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(MSG_INVALID_DATA, serializer.errors)
        
        try:
            result = PasswordRecoveryService.reset_password(
                email=serializer.validated_data['email'],
                code=serializer.validated_data['code'],
                new_password=serializer.validated_data['new_password']
            )
            return success_response(result, result['message'])
        except ValueError as e:
            return error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error resetting password: {e}')
            return error_response(
                'Error al restablecer la contraseña.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ---------------------------------------------------------------------------
# Teacher → Eligible groups  (Scenario 2 support)
# ---------------------------------------------------------------------------

class TeacherEligibleGroupsView(APIView):
    """
    GET /api/users/{pk}/eligible-groups/
    Returns active groups whose academic_level matches at least one subject
    level_number of the given teacher.  Only admins can access this endpoint.

    Response shape per item:
        id_group, group_letter, academic_level, generation_year,
        id_generation, subjects_at_level (list of subject names),
        assigned_teacher (null | {id_teacher, full_name})
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        summary='Grupos elegibles para un docente',
        tags=['Usuarios'],
        responses={
            200: OpenApiResponse(description='Lista de grupos elegibles'),
            400: OpenApiResponse(description='El usuario no es docente'),
            404: OpenApiResponse(description='Usuario no encontrado'),
        },
        description=(
            'Retorna los grupos activos cuyo nivel académico coincida con al '
            'menos una materia asignada al docente indicado.'
        ),
    )
    def get(self, request, pk):
        try:
            user = User.objects.select_related('teacher_profile').prefetch_related(
                'teacher_profile__subjects'
            ).get(pk=pk)
        except User.DoesNotExist:
            return error_response(MSG_USER_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)

        if user.role != 'teacher':
            return error_response(
                'El usuario especificado no tiene el rol de docente.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = user.teacher_profile
        except Exception:
            return success_response({'results': []})

        subject_levels = list(
            profile.subjects.filter(status=True).values_list('level_number', flat=True).distinct()
        )
        if not subject_levels:
            return success_response({'results': []})

        from apps.academic.models import Group, GroupTeacherAssignment
        from apps.academic.services import PeriodService

        groups = (
            Group.objects
            .filter(status=True, academic_level__in=subject_levels)
            .select_related('id_generation')
            .prefetch_related('teacher_assignments__teacher__user', 'teacher_assignments__subject')
        )

        results = []
        for g in groups:
            current_level = PeriodService.sync_group_academic_level(g)
            subjects_at_level = [
                s.name for s in profile.subjects.filter(level_number=current_level, status=True)
            ]
            assignments = [
                {
                    'id_assignment': a.pk,
                    'subject': {'id_subject': a.subject.pk, 'name': a.subject.name},
                    'teacher': {'id_teacher': a.teacher.pk, 'full_name': a.teacher.user.full_name},
                }
                for a in g.teacher_assignments.all()
            ]
            results.append({
                'id_group': g.pk,
                'group_letter': g.group_letter,
                'academic_level': current_level,
                'generation_year': g.id_generation.year,
                'id_generation': g.id_generation.pk,
                'subjects_at_level': subjects_at_level,
                'assignments': assignments,
            })

        logger.info(
            'Grupos elegibles para docente | user_id={} levels={} count={}',
            pk, subject_levels, len(results),
        )
        return success_response({'results': results})
