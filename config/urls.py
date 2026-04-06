"""
URL configuration for SEA-API project.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/auth/', include('apps.authentication.urls')),
    path('api/exams/', include('apps.exams.urls')),
    path('api/', include('apps.core.urls')),
    path('api/academic/', include('apps.academic.urls')),
    path('api/questions/', include('apps.questions.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/audit-logs/', include('apps.audit.urls')),
    
    # Swagger/OpenAPI documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
