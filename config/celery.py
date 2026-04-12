"""
Celery application configuration for SEA-API.

Uses Redis as the message broker. The broker URL is read from the
CELERY_BROKER_URL environment variable so credentials are never hardcoded.
"""

import os

from celery import Celery
from decouple import config as env_config

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('sea_api')

# Read Celery-specific settings from Django settings (prefixed with CELERY_).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks inside every installed app (looks for tasks.py).
app.autodiscover_tasks()
