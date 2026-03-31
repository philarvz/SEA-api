"""
Audit module views.
Implements the endpoint for querying audit log records.
"""

from loguru import logger
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import AuditLog
from .serializers import AuditLogSerializer
from utils.pagination import GlobalPagination
from utils.responses import error_response


class AuditLogListView(APIView):
    """
    GET /api/audit-logs/
    Lista paginada de registros de auditoría con filtros opcionales.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar registros de auditoría',
        tags=['Auditoría'],
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, description='Número de página', required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description='Registros por página (max: 100)', required=False),
            OpenApiParameter('table_name', OpenApiTypes.STR, description='Filtrar por nombre de tabla', required=False),
            OpenApiParameter('operation_type', OpenApiTypes.STR, description='Filtrar por tipo de operación (INSERT, UPDATE, DELETE)', required=False, enum=['INSERT', 'UPDATE', 'DELETE']),
            OpenApiParameter('changed_at_from', OpenApiTypes.DATETIME, description='Fecha inicio (ISO 8601)', required=False),
            OpenApiParameter('changed_at_to', OpenApiTypes.DATETIME, description='Fecha fin (ISO 8601)', required=False),
        ],
        responses={200: AuditLogSerializer(many=True)},
    )
    def get(self, request):
        try:
            queryset = AuditLog.objects.all()

            table_name = request.query_params.get('table_name')
            operation_type = request.query_params.get('operation_type')
            changed_at_from = request.query_params.get('changed_at_from')
            changed_at_to = request.query_params.get('changed_at_to')

            if table_name:
                queryset = queryset.filter(table_name=table_name)
            if operation_type:
                queryset = queryset.filter(operation_type=operation_type.upper())
            if changed_at_from:
                queryset = queryset.filter(changed_at__gte=changed_at_from)
            if changed_at_to:
                queryset = queryset.filter(changed_at__lte=changed_at_to)

            paginator = GlobalPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = AuditLogSerializer(paginated_queryset, many=True)

            return paginator.get_paginated_response(serializer.data)

        except Exception as exc:
            logger.error('Error listing audit logs | {}', exc)
            return error_response(
                'Error al obtener los registros de auditoría.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
