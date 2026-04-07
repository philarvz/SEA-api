"""
Academic module service layer.
Encapsulates business logic that is too complex or cross-cutting for views.
"""

from django.utils import timezone

from .models import Period, Group


class PeriodService:
    """Business logic for Period management."""

    TERMS_PER_YEAR = 3
    START_TERM_INDEX = 3
    PERIOD_INDEX_BY_NAME = {
        'Enero-Abril': 1,
        'Mayo-Agosto': 2,
        'Septiembre-Diciembre': 3,
    }

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

    @classmethod
    def get_current_period_index(cls):
        """
        Resolve current term index using configured periods.
        Falls back to month ranges when there is no active period configured.
        """
        current_period = cls.get_current_period()
        if current_period:
            return cls.PERIOD_INDEX_BY_NAME.get(current_period.period_name, cls.START_TERM_INDEX)

        month = timezone.now().date().month
        if month <= 4:
            return 1
        if month <= 8:
            return 2
        return 3

    @classmethod
    def calculate_generation_academic_level(cls, generation_year, total_levels):
        """
        Calculate academic level using generation year and current period index.
        Result is clamped between 1 and total_levels.
        """
        safe_total_levels = max(1, int(total_levels or 1))
        current_year = timezone.now().date().year
        current_period_index = cls.get_current_period_index()

        elapsed_terms = ((current_year - int(generation_year)) * cls.TERMS_PER_YEAR) + (
            current_period_index - cls.START_TERM_INDEX
        )
        raw_level = elapsed_terms + 1
        return min(max(raw_level, 1), safe_total_levels)

    @classmethod
    def sync_group_academic_level(cls, group):
        """
        Recalculate and persist academic level for a single group when needed.
        Returns the resulting level.
        """
        expected_level = cls.calculate_generation_academic_level(
            generation_year=group.id_generation.year,
            total_levels=group.id_generation.total_levels,
        )
        if group.academic_level != expected_level:
            group.academic_level = expected_level
            group.save(update_fields=['academic_level'])
        return expected_level

    @classmethod
    def sync_all_groups_academic_level(cls):
        """
        Recalculate all groups academic levels according to current date/period.
        Returns the number of groups updated.
        """
        updated_count = 0
        groups = Group.objects.select_related('id_generation').all()
        for group in groups:
            previous_level = group.academic_level
            expected_level = cls.sync_group_academic_level(group)
            if previous_level != expected_level:
                updated_count += 1
        return updated_count

    @staticmethod
    def advance_groups_academic_level():
        """
        Backward-compatible hook used by existing endpoint.
        Recalculates levels based on current date/period rules.

        Returns:
            int: Number of groups that were updated.
        """
        return PeriodService.sync_all_groups_academic_level()
