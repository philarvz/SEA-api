"""
Utility script to auto-generate the three reusable academic periods.
Since periods no longer have a year field, this script creates the three
base periods (Enero-Abril, Mayo-Agosto, Septiembre-Diciembre) once.

Usage:
    python scripts/generate_periods.py
"""

import sys
import os
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.academic.models import Period
from loguru import logger


PERIOD_NAMES = [
    'Enero-Abril',
    'Mayo-Agosto',
    'Septiembre-Diciembre',
]


def generate_periods():
    """
    Generate the three reusable academic periods.
    Skips periods that already exist.
    """
    created_count = 0
    skipped_count = 0

    for period_name in PERIOD_NAMES:
        period, created = Period.objects.get_or_create(
            period_name=period_name,
            defaults={'status': True}
        )
        
        if created:
            created_count += 1
            logger.info(f'Created period: {period}')
            print(f'✓ Created: {period_name}')
        else:
            skipped_count += 1
            print(f'- Skipped (already exists): {period_name}')

    print(f'\n Summary:')
    print(f'  Created: {created_count} period(s)')
    print(f'  Skipped: {skipped_count} period(s) (already existed)')
    
    return created_count


if __name__ == '__main__':
    print('Generating reusable academic periods...\n')
    generate_periods()
