"""
Academic module models
Includes: Generation, Period, Group, Subject, Unit
"""

from django.db import models
from django.core.exceptions import ValidationError

from apps.core.base_models import BaseAuditModel


class Generation(BaseAuditModel):
    """
    Academic generation (cohorte): students who enter the same year and
    progress together through the programme.
    total_levels defines how many academic levels this generation will complete.
    """
    id_generation = models.AutoField(primary_key=True, db_column='id_generation')
    year = models.IntegerField(unique=True)
    total_levels = models.PositiveIntegerField(default=11, db_column='total_levels')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'generation'
        verbose_name = 'Generation'
        verbose_name_plural = 'Generations'
        ordering = ['-year']

    def __str__(self):
        return f"Generation {self.year}"


class Period(BaseAuditModel):
    """
    Academic period: one of three reusable terms (Enero-Abril, Mayo-Agosto,
    Septiembre-Diciembre). Each period is created once and reused every year.
    Dates are calculated automatically using the current year:
    - Enero-Abril: Jan 1 - Apr 30
    - Mayo-Agosto: May 1 - Aug 31
    - Septiembre-Diciembre: Sep 1 - Dec 31
    Academic level progression occurs automatically at 12:00 AM on the first day of each period.
    """
    PERIOD_CHOICES = [
        ('Enero-Abril', 'Enero-Abril'),
        ('Mayo-Agosto', 'Mayo-Agosto'),
        ('Septiembre-Diciembre', 'Septiembre-Diciembre'),
    ]

    id_period = models.AutoField(primary_key=True, db_column='id_period')
    period_name = models.CharField(
        max_length=50, choices=PERIOD_CHOICES, db_column='period_name', unique=True
    )
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'period'
        verbose_name = 'Period'
        verbose_name_plural = 'Periods'
        ordering = ['period_name']

    def __str__(self):
        return f"{self.period_name}"

    @property
    def start_date(self):
        """Calculate start date based on period_name and current year."""
        from datetime import date
        from django.utils import timezone
        month_map = {
            'Enero-Abril': 1,
            'Mayo-Agosto': 5,
            'Septiembre-Diciembre': 9,
        }
        month = month_map.get(self.period_name, 1)
        current_year = timezone.now().date().year
        return date(current_year, month, 1)

    @property
    def end_date(self):
        """Calculate end date based on period_name and current year."""
        from datetime import date
        import calendar
        from django.utils import timezone
        end_month_map = {
            'Enero-Abril': 4,
            'Mayo-Agosto': 8,
            'Septiembre-Diciembre': 12,
        }
        end_month = end_month_map.get(self.period_name, 4)
        current_year = timezone.now().date().year
        last_day = calendar.monthrange(current_year, end_month)[1]
        return date(current_year, end_month, last_day)


class Group(BaseAuditModel):
    """
    Academic group belonging to a generation.
    Tracks the group letter (A, B, C…) and the current academic level.
    The academic_level must be between 1 and generation.total_levels.
    Academic level progression is derived from current date/period rules.
    Teacher assignments are managed through GroupTeacherAssignment (M:N through).
    """
    id_group = models.AutoField(primary_key=True, db_column='id_group')
    id_generation = models.ForeignKey(
        Generation,
        on_delete=models.RESTRICT,
        db_column='id_generation',
        related_name='groups',
    )
    group_letter = models.CharField(max_length=5, db_column='group_letter')
    academic_level = models.PositiveIntegerField(db_column='academic_level')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'group'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['id_generation', 'group_letter']
        unique_together = [['id_generation', 'group_letter']]

    def clean(self):
        if self.academic_level < 1:
            raise ValidationError('academic_level must be at least 1.')
        if self.id_generation and self.academic_level > self.id_generation.total_levels:
            raise ValidationError(
                f'academic_level cannot exceed generation total_levels ({self.id_generation.total_levels}).'
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_level}{self.group_letter} (Gen {self.id_generation.year})"


class Subject(BaseAuditModel):
    """
    Subject associated to a specific level number.
    level_number represents the academic level where the subject is taught.
    """
    id_subject = models.AutoField(primary_key=True, db_column='id_subject')
    name = models.CharField(max_length=150)
    level_number = models.PositiveIntegerField(db_column='level_number')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'subject'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['level_number', 'name']

    def __str__(self):
        return f"{self.name} (L{self.level_number})"


class Unit(BaseAuditModel):
    """
    Thematic unit belonging to a subject.
    """
    id_unit = models.AutoField(primary_key=True, db_column='id_unit')
    id_subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        db_column='id_subject',
        related_name='units',
    )
    unit_name = models.CharField(max_length=150, db_column='unit_name')
    unit_number = models.IntegerField(db_column='unit_number')

    class Meta:
        db_table = 'unit'
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'

    def __str__(self):
        return f"Unit {self.unit_number}: {self.unit_name}"


class GroupTeacherAssignment(BaseAuditModel):
    """
    Many-to-many assignment between a Group and a TeacherProfile via a Subject.
    Each subject in a group has at most one teacher (unique_together on group+subject).
    A group can have multiple teachers — one per subject at its academic level.
    """
    id_assignment = models.AutoField(primary_key=True, db_column='id_assignment')
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column='group_id',
        related_name='teacher_assignments',
    )
    teacher = models.ForeignKey(
        'users.TeacherProfile',
        on_delete=models.CASCADE,
        db_column='teacher_id',
        related_name='group_assignments',
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        db_column='subject_id',
        related_name='group_assignments',
    )

    class Meta:
        db_table = 'group_teacher_assignment'
        verbose_name = 'Group Teacher Assignment'
        verbose_name_plural = 'Group Teacher Assignments'
        unique_together = [['group', 'subject']]  # one teacher per subject per group

    def __str__(self):
        return f"{self.group} | {self.subject.name} → {self.teacher}"
