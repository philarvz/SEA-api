"""
Exams module models
Includes: Exam, ExamQuestion, ExamPerson
"""

from django.db import models


class Exam(models.Model):
    """
    Model representing an exam
    """
    id_exam = models.AutoField(primary_key=True, db_column='id_exam')
    id_subject = models.ForeignKey(
        'academic.Subject',
        on_delete=models.RESTRICT,
        db_column='id_subject',
        related_name='exams'
    )
    id_teacher = models.ForeignKey(
        'users.Person',
        on_delete=models.RESTRICT,
        db_column='id_teacher',
        related_name='created_exams'
    )
    title = models.CharField(max_length=200)
    secure_mode = models.BooleanField(default=False, db_column='secure_mode')
    creation_date = models.DateField(db_column='creation_date')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'exam'
        verbose_name = 'Exam'
        verbose_name_plural = 'Exams'
        ordering = ['-creation_date']

    def __str__(self):
        return self.title


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
        'users.Person',
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
