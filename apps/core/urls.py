"""
Core URL Configuration
"""

from django.urls import path
from .views import ApiRootView

app_name = 'core'

urlpatterns = [
    path('', ApiRootView.as_view(), name='api-root'),
]
