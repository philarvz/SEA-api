from django.db import models


class AuditLog(models.Model):
    table_name = models.TextField()
    operation_type = models.TextField()

    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    db_user = models.TextField(null=True, blank=True)
    app_user = models.TextField(null=True, blank=True)
    client_addr = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'audit_log'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.table_name} - {self.operation_type} - {self.changed_at}"
