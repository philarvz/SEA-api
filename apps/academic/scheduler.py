"""
Academic Level Scheduler
Automatically advances academic levels for all groups on the first day of each period.

Scheduled execution dates:
- January 1 at 00:00 (Periodo Enero-Abril)
- May 1 at 00:00 (Periodo Mayo-Agosto)
- September 1 at 00:00 (Periodo Septiembre-Diciembre)
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.utils import timezone
from loguru import logger

from apps.academic.services import PeriodService


def advance_academic_levels_job():
    """
    Job to advance academic levels for all active groups.
    This function is executed automatically by APScheduler on period start dates.
    """
    try:
        current_date = timezone.now().date()
        logger.info(f'Starting scheduled academic level advancement | date={current_date}')
        
        updated_count = PeriodService.advance_groups_academic_level()
        
        logger.info(
            f'Academic levels advanced successfully | '
            f'date={current_date} groups_updated={updated_count}'
        )
        
        return updated_count
        
    except Exception as e:
        logger.error(f'Error advancing academic levels | error={str(e)}')
        raise


def start_scheduler():
    """
    Initialize and start the APScheduler for academic level advancement.
    The scheduler runs in the background and executes the job on:
    - January 1 at 00:00
    - May 1 at 00:00
    - September 1 at 00:00
    """
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    
    # Create a cron trigger for the first day of January, May, and September at midnight
    trigger = CronTrigger(
        month='1,5,9',  # January, May, September
        day=1,          # First day of the month
        hour=0,         # Midnight
        minute=0,
        timezone=settings.TIME_ZONE
    )
    
    # Add the job to the scheduler
    scheduler.add_job(
        advance_academic_levels_job,
        trigger=trigger,
        id='advance_academic_levels',
        name='Advance Academic Levels',
        replace_existing=True,
        max_instances=1,  # Prevent concurrent executions
    )
    
    scheduler.start()
    
    logger.info(
        'Academic level scheduler started | '
        f'next_run={scheduler.get_job("advance_academic_levels").next_run_time}'
    )
    
    return scheduler
