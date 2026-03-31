"""
Users module URL configuration
"""

from django.urls import path
from .views import UserListCreateView, UserDetailView, UserStatusView

app_name = 'users'

urlpatterns = [
    path('', UserListCreateView.as_view(), name='user-list-create'),
    path('<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('<int:pk>/status/', UserStatusView.as_view(), name='user-status'),
]
