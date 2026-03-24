"""
Users module URL configuration
"""

from django.urls import path
from .views import RegisterUserView

app_name = 'users'

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
]
