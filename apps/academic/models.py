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
    Academic period: one of three annual terms (Enero-Abril, Mayo-Agosto,
    Septiembre-Diciembre).  The current period is determined dynamically by
    comparing today's date against start_date / end_date.
    """
    PERIOD_CHOICES = [
        ('Enero-Abril', 'Enero-Abril'),
        ('Mayo-Agosto', 'Mayo-Agosto'),
        ('Septiembre-Diciembre', 'Septiembre-Diciembre'),
    ]

    id_period = models.AutoField(primary_key=True, db_column='id_period')
    year = models.IntegerField()
    period_name = models.CharField(
        max_length=50, choices=PERIOD_CHOICES, db_column='period_name'
    )
    start_date = models.DateField(db_column='start_date')
    end_date = models.DateField(db_column='end_date')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'period'
        verbose_name = 'Period'
        verbose_name_plural = 'Periods'
        ordering = ['-year', 'period_name']
        unique_together = [['year', 'period_name']]

    def __str__(self):
        return f"{self.year} - {self.period_name}"


class Group(BaseAuditModel):
    """
    Academic group belonging to a generation.
    Tracks the group letter (A, B, C…) and the current academic level.
    The academic_level must be between 1 and generation.total_levels.
    The active period is automatically captured at creation time.
    """
    id_group = models.AutoField(primary_key=True, db_column='id_group')
    id_generation = models.ForeignKey(
        Generation,
        on_delete=models.RESTRICT,
        db_column='id_generation',
        related_name='groups',
    )
    id_period = models.ForeignKey(
        Period,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='id_period',
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
