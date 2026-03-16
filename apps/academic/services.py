"""
Academic module service layer.
Encapsulates business logic that is too complex or cross-cutting for views.
"""

from django.utils import timezone
from django.db.models import Max, F

from .models import Period, Group, Generation


class PeriodService:
    """Business logic for Period management."""

    @staticmethod
    def get_current_period():
        """
        Determine the current academic period by comparing today's date
        against the registered start_date / end_date ranges.

        Returns:
            Period | None: The active period whose range contains today,
                           or None if no matching period is found.
        """
        today = timezone.now().date()
        return Period.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            status=True,
        ).first()

    @staticmethod
    def advance_groups_academic_level():
        """
        Increment the academic_level of all active groups by 1.
        Groups that have already reached their generation's total_levels are
        excluded to avoid exceeding valid levels.

        The maximum academic_level for each group is determined by its 
        generation's total_levels field, which is the authoritative registry
        of valid programme levels for that specific generation.

        Returns:
            int: Number of groups that were updated.
        """
        updated_count = (
            Group.objects
            .filter(status=True, academic_level__lt=F('id_generation__total_levels'))
            .update(academic_level=F('academic_level') + 1)
        )
        return updated_count
