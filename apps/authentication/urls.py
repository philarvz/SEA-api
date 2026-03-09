"""
Authentication URL Configuration
"""

from django.urls import path
from .views import LoginView, TokenRefreshView, HealthCheckView

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
