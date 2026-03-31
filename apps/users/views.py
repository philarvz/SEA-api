from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django.contrib.auth import get_user_model
from django.db import models

from .permissions import IsAdmin
from .serializers import RegisterUserSerializer, UserResponseSerializer, UserListSerializer, UpdateUserSerializer
from .services import UserRegistrationService, UserUpdateService
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
        ],
        responses={
            200: UserListSerializer(many=True),
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Obtiene un listado paginado de todos los usuarios del sistema. '
            'Solo los administradores pueden acceder. '
            'Soporta filtros por rol, estado y búsqueda por texto.'
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
            'La contraseña se genera automáticamente y se envía al correo del usuario.'
        ),
    )
    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                'User registration rejected | errors={}', serializer.errors
            )
            return error_response('Datos inválidos.', serializer.errors)

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
                'Usuario no encontrado.',
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
                'Usuario no encontrado.',
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
            return error_response('Datos inválidos.', serializer.errors)
        
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
