from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict


class GlobalPagination(PageNumberPagination):
    """
    Paginador global con configuración estándar para toda la aplicación.
    
    Parámetros de consulta:
        - page: Número de página (default: 1)
        - page_size: Registros por página (default: 10, max: 100)
    
    Respuesta estructurada:
        {
            "count": <total de registros>,
            "total_pages": <total de páginas>,
            "current_page": <página actual>,
            "page_size": <registros por página>,
            "next": <url de siguiente página o null>,
            "previous": <url de página anterior o null>,
            "results": [<array de resultados>]
        }
    """
    
    page_size = 10  # Tamaño por defecto
    page_size_query_param = 'page_size'  # Parámetro para cambiar el tamaño
    max_page_size = 100  # Tamaño máximo permitido
    page_query_param = 'page'  # Parámetro de página
    
    def get_paginated_response(self, data):
        """
        Estructura personalizada de respuesta con metadatos de paginación.
        """
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))
    
    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 150,
                    'description': 'Total de registros en la base de datos'
                },
                'total_pages': {
                    'type': 'integer',
                    'example': 15,
                    'description': 'Total de páginas disponibles'
                },
                'current_page': {
                    'type': 'integer',
                    'example': 1,
                    'description': 'Número de página actual'
                },
                'page_size': {
                    'type': 'integer',
                    'example': 10,
                    'description': 'Registros por página'
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': 'http://api.example.com/resource?page=2',
                    'description': 'URL de la siguiente página (null si es la última)'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': None,
                    'description': 'URL de la página anterior (null si es la primera)'
                },
                'results': schema,
            },
        }
