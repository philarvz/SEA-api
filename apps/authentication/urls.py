"""
Authentication URL Configuration
"""

from django.urls import path
from .views import LoginView, TokenRefreshView, HealthCheckView, ChangePasswordView

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
