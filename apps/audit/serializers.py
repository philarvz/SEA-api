"""
Serializers for the Audit module.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import AuditLog

User = get_user_model()


class AuditLogSerializer(serializers.ModelSerializer):
    app_user_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'table_name',
            'operation_type',
            'old_values',
            'new_values',
            'changed_at',
            'app_user',
            'app_user_name',
            'client_addr',
        ]
        read_only_fields = fields

    def get_app_user_name(self, obj):
        if obj.app_user and obj.app_user not in ('anonymous', ''):
            try:
                user = User.objects.get(pk=obj.app_user)
                return user.get_full_name() or user.username
            except (User.DoesNotExist, ValueError):
                pass
        return obj.app_user
