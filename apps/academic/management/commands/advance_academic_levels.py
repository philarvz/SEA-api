"""
Management command: Advance academic levels for all groups.
This command should be scheduled to run automatically at 12:00 AM on:
- January 1 (start of Enero-Abril period)
- May 1 (start of Mayo-Agosto period)  
- September 1 (start of Septiembre-Diciembre period)

Usage:
    python manage.py advance_academic_levels

Windows Task Scheduler configuration example:
    Schedule for: 01/01 00:00, 05/01 00:00, 09/01 00:00
    Action: Start a program
    Program: C:\\path\\to\\python.exe
    Arguments: C:\\path\\to\\manage.py advance_academic_levels
    Start in: C:\\path\\to\\project\\

Linux cron configuration example:
    # Run at 00:00 on January 1, May 1, September 1
    0 0 1 1,5,9 * cd /path/to/project && /path/to/venv/bin/python manage.py advance_academic_levels
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from loguru import logger

from apps.academic.services import PeriodService


class Command(BaseCommand):
    help = 'Advance academic levels for all active groups based on current period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the operation without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        current_date = timezone.now().date()
        self.stdout.write(f'Running academic level advancement for date: {current_date}')
        
        # Check if today is the first day of a period (Jan 1, May 1, or Sep 1)
        is_period_start = (
            (current_date.month == 1 and current_date.day == 1) or
            (current_date.month == 5 and current_date.day == 1) or
            (current_date.month == 9 and current_date.day == 1)
        )
        
        if not is_period_start and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Today ({current_date}) is not the first day of a period. '
                    'Academic levels should only advance on Jan 1, May 1, or Sep 1.'
                )
            )
            # In production, you may want to exit here
            # For now, we'll continue to allow manual execution for testing
        
        try:
            if dry_run:
                from apps.academic.models import Group
                groups = Group.objects.select_related('id_generation').all()
                would_update_count = 0
                
                self.stdout.write('\nGroups that would be updated:')
                for group in groups:
                    expected_level = PeriodService.calculate_generation_academic_level(
                        generation_year=group.id_generation.year,
                        total_levels=group.id_generation.total_levels,
                    )
                    if group.academic_level != expected_level:
                        would_update_count += 1
                        self.stdout.write(
                            f'  - {group} | Current level: {group.academic_level} → '
                            f'Expected level: {expected_level}'
                        )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nDRY RUN: Would update {would_update_count} group(s)'
                    )
                )
            else:
                updated_count = PeriodService.advance_groups_academic_level()
                
                logger.info(
                    'Academic levels advanced via management command | '
                    f'date={current_date} groups_updated={updated_count}'
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully advanced academic levels for {updated_count} group(s)'
                    )
                )
                
        except Exception as exc:
            error_msg = f'Error advancing academic levels: {exc}'
            logger.error(error_msg)
            self.stdout.write(self.style.ERROR(error_msg))
            raise
