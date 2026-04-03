"""
Exams module models
Includes: Exam, ExamQuestion, ExamAssignment
Note: id_teacher references users.User (AbstractUser)
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
    minimum_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=8.00,
        db_column='minimum_score',
        help_text='Calificación mínima para aprobar el examen.',
    )
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


class ExamAssignment(models.Model):
    """
    Represents the assignment of an exam to an individual student,
    generated when a teacher assigns an exam to one or more groups.
    Each record tracks the student's exam lifecycle: availability window,
    attempt status, score and pass/fail result.
    """
    ASSIGNMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
    ]

    id_assignment = models.AutoField(primary_key=True, db_column='id')
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='exam_assignments',
    )
    student = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_column='student_id',
        related_name='exam_assignments',
    )
    group = models.ForeignKey(
        'academic.Group',
        on_delete=models.RESTRICT,
        db_column='group_id',
        related_name='exam_assignments',
    )
    status = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_STATUS_CHOICES,
        default='pending',
        db_column='status',
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, db_column='score',
    )
    is_passed = models.BooleanField(null=True, blank=True, db_column='is_passed')
    assigned_at = models.DateTimeField(db_column='assigned_at')
    available_from = models.DateTimeField(db_column='available_from')
    available_to = models.DateTimeField(db_column='available_to')
    attempt_date = models.DateTimeField(
        null=True, blank=True, db_column='attempt_date',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'exam_assignment'
        verbose_name = 'Exam Assignment'
        verbose_name_plural = 'Exam Assignments'
        unique_together = [['exam', 'student']]
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Exam {self.exam_id} → Student {self.student_id} (Group {self.group_id})"


class ExamGroupAssignment(models.Model):
    """
    Tracks group-level exam assignments (independent of students).
    Guarantees that groups with zero students still appear in queries.
    """
    id_exam_group = models.AutoField(primary_key=True, db_column='id')
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        db_column='exam_id',
        related_name='group_assignments',
    )
    group = models.ForeignKey(
        'academic.Group',
        on_delete=models.RESTRICT,
        db_column='group_id',
        related_name='exam_group_assignments',
    )
    available_from = models.DateTimeField(db_column='available_from')
    available_to = models.DateTimeField(db_column='available_to')
    assigned_at = models.DateTimeField(auto_now_add=True, db_column='assigned_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'exam_group_assignment'
        verbose_name = 'Exam Group Assignment'
        verbose_name_plural = 'Exam Group Assignments'
        unique_together = [['exam', 'group']]
        ordering = ['group']

    def __str__(self):
        return f"Exam {self.exam_id} → Group {self.group_id}"
