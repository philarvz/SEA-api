# Ensure the Celery app is imported when Django starts so that
# @shared_task decorators use this app instance.
from .celery import app as celery_app

__all__ = ['celery_app']
