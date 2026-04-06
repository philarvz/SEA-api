"""
Reusable abstract model mixins for domain models.
"""

from django.conf import settings
from django.db import models


class BaseAuditModifiedModel(models.Model):
    """
    Modification audit only (no ``created_at``).

    Use when the model already has a domain creation field (e.g. ``DateField``)
    and you want to avoid duplicating creation timestamps.

    ``modified_by`` is set from ``get_current_user()`` when the request has an
    authenticated user (see ``RequestContextMiddleware``).
    """

    modified_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_modified_by_set',
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from apps.core.thread_local import get_current_user

        user = get_current_user()
        if user is not None:
            self.modified_by = user
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                update_fields = list(update_fields)
                if 'modified_by' not in update_fields:
                    update_fields.append('modified_by')
                kwargs['update_fields'] = update_fields
        super().save(*args, **kwargs)


class BaseAuditModel(BaseAuditModifiedModel):
    """
    Full audit: creation and modification instants (timestamps) plus last modifier.

    Inherits ``save()`` behaviour from ``BaseAuditModifiedModel`` for ``modified_by``.
    """

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        abstract = True
