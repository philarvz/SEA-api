"""
Academic module models
Includes: Term, Group, Subject, Unit
"""

from django.db import models


class Term(models.Model):
    """
    Model representing an academic term (cuatrimestre)
    """
    id_term = models.AutoField(primary_key=True, db_column='id_term')
    term_name = models.CharField(max_length=100, db_column='term_name')
    start_date = models.DateField(db_column='start_date')
    end_date = models.DateField(db_column='end_date')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'term'
        verbose_name = 'Term'
        verbose_name_plural = 'Terms'
        ordering = ['-start_date']

    def __str__(self):
        return self.term_name


class Group(models.Model):
    """
    Model representing a student group
    """
    id_group = models.AutoField(primary_key=True, db_column='id_group')
    id_term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        db_column='id_term',
        related_name='groups'
    )
    group_name = models.CharField(max_length=100, db_column='group_name')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'group'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['group_name']

    def __str__(self):
        return f"{self.group_name} - {self.id_term.term_name}"


class Subject(models.Model):
    """
    Model representing a subject or course
    """
    id_subject = models.AutoField(primary_key=True, db_column='id_subject')
    id_term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        db_column='id_term',
        related_name='subjects'
    )
    name = models.CharField(max_length=150)
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'subject'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['name']

    def __str__(self):
        return self.name


class Unit(models.Model):
    """
    Model representing a thematic unit of a subject
    """
    id_unit = models.AutoField(primary_key=True, db_column='id_unit')
    id_subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        db_column='id_subject',
        related_name='units'
    )
    unit_name = models.CharField(max_length=150, db_column='unit_name')
    unit_number = models.IntegerField(db_column='unit_number')

    class Meta:
        db_table = 'unit'
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'
        ordering = ['id_subject', 'unit_number']

    def __str__(self):
        return f"Unit {self.unit_number}: {self.unit_name}"
