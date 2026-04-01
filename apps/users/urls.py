"""
Users module URL configuration
"""

from django.urls import path
from .views import (
    UserListCreateView, 
    UserDetailView, 
    UserStatusView,
    RequestPasswordResetView,
    VerifyResetCodeView,
    ResetPasswordView,
)

app_name = 'users'

urlpatterns = [
    path('', UserListCreateView.as_view(), name='user-list-create'),
    path('<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('<int:pk>/status/', UserStatusView.as_view(), name='user-status'),
    
    # Password recovery endpoints
    path('password-recovery/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password-recovery/verify/', VerifyResetCodeView.as_view(), name='password-reset-verify'),
    path('password-recovery/reset/', ResetPasswordView.as_view(), name='password-reset'),
]
