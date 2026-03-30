"""
Users module URL configuration
"""

from django.urls import path
from .views import RegisterUserView, ListUsersView

app_name = 'users'

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('', ListUsersView.as_view(), name='list-users'),
]
