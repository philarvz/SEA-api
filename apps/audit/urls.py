"""
URL configuration for the Audit module.
Base path: /api/audit-logs/
"""

from django.urls import path
from .views import AuditLogListView

app_name = 'audit'

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-log-list'),
]
