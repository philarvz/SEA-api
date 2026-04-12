"""
Core Views
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema


class ApiRootView(APIView):
    """
    GET api/v1/
    
    API Root endpoint - provides information about available endpoints
    """
    permission_classes = [AllowAny]
    
    @extend_schema(exclude=True)
    def get(self, request):
        """
        Get API information
        
        Response:
            - name: API name
            - version: API version
            - endpoints: Available endpoints
        """
        return Response({
            'name': 'SEA-API',
            'version': '1.0.0',
            'description': 'Service-based REST API with JWT Authentication',
            'endpoints': {
                'authentication': '/api/v1/auth/',
                'login': '/api/v1/auth/login/',
                'refresh': '/api/v1/auth/refresh/',
                'health': '/api/v1/auth/health/',
            }
        }, status=status.HTTP_200_OK)
