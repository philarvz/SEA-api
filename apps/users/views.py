from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from django.contrib.auth import get_user_model
from django.db import models

from .permissions import IsAdmin
from .serializers import RegisterUserSerializer, UserResponseSerializer, UserListSerializer
from .services import UserRegistrationService
from utils.responses import success_response, error_response
from utils.pagination import GlobalPagination

User = get_user_model()


class RegisterUserView(APIView):

    permission_classes = [IsAdmin]

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


class ListUsersView(ListAPIView):

    permission_classes = [IsAdmin]
    serializer_class = UserListSerializer
    pagination_class = GlobalPagination

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
            200: UserListSerializer,
            403: OpenApiResponse(description='Se requiere rol de administrador'),
            500: OpenApiResponse(description='Error interno del servidor'),
        },
        description=(
            'Obtiene un listado paginado de todos los usuarios del sistema. '
            'Solo los administradores pueden acceder. '
            'Soporta filtros por rol, estado y búsqueda por texto.'
        ),
    )
    def get(self, request, *args, **kwargs):
        try:
            logger.info(
                'Listing users | requester={} page={} page_size={}',
                request.user.username,
                request.query_params.get('page', 1),
                request.query_params.get('page_size', 10),
            )
            return super().get(request, *args, **kwargs)
        except Exception as exc:
            logger.error('Error listing users | {}', exc)
            return error_response(
                'Error al obtener el listado de usuarios.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_queryset(self):
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
        role = self.request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
            logger.debug('Filtering by role | role={}', role)

        # Filtro por estado
        status_param = self.request.query_params.get('status', None)
        if status_param is not None:
            status_bool = status_param.lower() == 'true'
            queryset = queryset.filter(status=status_bool)
            logger.debug('Filtering by status | status={}', status_bool)

        # Búsqueda por texto
        search = self.request.query_params.get('search', None)
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
