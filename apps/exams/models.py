"""
Exams module models
Includes: Exam, ExamQuestion, ExamPerson
Note: id_teacher and id_person now reference users.User (AbstractUser)
"""

from django.db import models
from django.core.exceptions import ValidationError


class Exam(models.Model):
    """
    Model representing an exam.
    An exam is created over a subject, a valid unit within that subject,
    and a difficulty level.  This base configuration is later populated
    with questions and assigned to students.
    """
    DIFFICULTY_CHOICES = [
        ('easy', 'Fácil'),
        ('medium', 'Medio'),
        ('hard', 'Difícil'),
    ]

    id_exam = models.AutoField(primary_key=True, db_column='id_exam')
    name = models.CharField(max_length=200, db_column='name', default='')
    id_subject = models.ForeignKey(
        'academic.Subject',
        on_delete=models.RESTRICT,
        db_column='id_subject',
        related_name='exams'
    )
    id_teacher = models.ForeignKey(
        'users.User',
        on_delete=models.RESTRICT,
        db_column='id_teacher',
        related_name='created_exams'
    )
    title = models.CharField(max_length=200)
    unit_number = models.PositiveIntegerField(db_column='unit_number', default=1)
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='medium',
        db_column='difficulty_level',
    )
    secure_mode = models.BooleanField(default=False, db_column='secure_mode')
    creation_date = models.DateField(db_column='creation_date')
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at', null=True)
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at', null=True)

    class Meta:
        db_table = 'exam'
        verbose_name = 'Exam'
        verbose_name_plural = 'Exams'
        ordering = ['-creation_date']

    def clean(self):
        """Validate that unit_number is within the subject's unit range."""
        if self.id_subject_id:
            max_units = self.id_subject.units.count()
            if max_units > 0 and self.unit_number > max_units:
                raise ValidationError({
                    'unit_number': (
                        f'La unidad {self.unit_number} excede el número de unidades '
                        f'de la materia ({max_units}).'
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.title


class ExamQuestion(models.Model):
    """
    Junction model relating exams with questions
    Defines the order of questions in the exam
    """
    id_exam_question = models.AutoField(
        primary_key=True,
        db_column='id_exam_question'
    )
    id_exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='id_exam',
        related_name='exam_questions'
    )
    id_question = models.ForeignKey(
        'questions.Question',
        on_delete=models.RESTRICT,
        db_column='id_question',
        related_name='question_exams'
    )
    question_order = models.IntegerField(db_column='question_order')

    class Meta:
        db_table = 'exam_question'
        verbose_name = 'Exam Question'
        verbose_name_plural = 'Exam Questions'
        unique_together = [['id_exam', 'id_question']]
        ordering = ['id_exam', 'question_order']

    def __str__(self):
        return f"{self.id_exam.title} - Question {self.question_order}"


class ExamPerson(models.Model):
    """
    Model representing the assignment of an exam to a student
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('finished', 'Finished'),
        ('not_presented', 'Not Presented'),
    ]

    id_exam_person = models.AutoField(
        primary_key=True,
        db_column='id_exam_person'
    )
    id_exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='id_exam',
        related_name='assignments'
    )
    id_person = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='id_person',
        related_name='assigned_exams'
    )
    assignment_date = models.DateField(db_column='assignment_date')
    start_datetime = models.DateTimeField(null=True, blank=True, db_column='start_datetime')
    end_datetime = models.DateTimeField(null=True, blank=True, db_column='end_datetime')
    grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'exam_person'
        verbose_name = 'Exam Person'
        verbose_name_plural = 'Exam Persons'
        unique_together = [['id_exam', 'id_person']]
        ordering = ['-assignment_date']

    def __str__(self):
        return f"{self.id_person.full_name} - {self.id_exam.title}"
