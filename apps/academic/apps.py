from django.apps import AppConfig


class AcademicConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.academic'
    verbose_name = 'Académico'
    
    def ready(self):
        """
        Initialize the academic level scheduler when the app is ready.
        The scheduler automatically advances academic levels on:
        - January 1 at 00:00
        - May 1 at 00:00
        - September 1 at 00:00
        """
        from django.conf import settings
        
        if settings.APSCHEDULER_ENABLED:
            from apps.academic.scheduler import start_scheduler
            try:
                start_scheduler()
            except Exception as e:
                from loguru import logger
                logger.error(f'Failed to start academic scheduler | error={str(e)}')
