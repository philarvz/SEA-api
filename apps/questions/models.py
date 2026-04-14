"""
Questions module models
Includes: Question, Answer, CodeQuestion
"""

from django.db import models

from apps.core.base_models import BaseAuditModel


class Question(BaseAuditModel):
    """
    Model representing an exam question (bank).
    """
    QUESTION_TYPE_CHOICES = [
        ('MULTIPLE_CHOICE', 'Multiple choice'),
        ('MULTIPLE_SELECTION', 'Multiple selection'),
        ('OPEN', 'Open'),
        ('CODE', 'Code'),
    ]

    BLOOM_LEVEL_CHOICES = [
        ('remember', 'Remember'),
        ('understand', 'Understand'),
        ('apply', 'Apply'),
        ('analyze', 'Analyze'),
        ('evaluate', 'Evaluate'),
        ('create', 'Create'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Fácil'),
        ('medium', 'Medio'),
        ('hard', 'Difícil'),
    ]

    id_question = models.AutoField(primary_key=True, db_column='id_question')
    id_subject = models.ForeignKey(
        'academic.Subject',
        on_delete=models.CASCADE,
        db_column='id_subject',
        related_name='questions',
    )
    statement = models.TextField()
    question_type = models.CharField(
        max_length=32,
        choices=QUESTION_TYPE_CHOICES,
        default='MULTIPLE_CHOICE',
        db_column='question_type',
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='medium',
        db_column='difficulty',
    )
    bloom_level = models.CharField(
        max_length=50,
        choices=BLOOM_LEVEL_CHOICES,
        db_column='bloom_level',
    )
    image_url = models.URLField(max_length=500, blank=True, null=True, db_column='image_url')
    points = models.PositiveSmallIntegerField(default=1, db_column='points')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'question'
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['-id_question']

    def __str__(self):
        return f"Question {self.id_question}: {self.statement[:50]}..."


class Answer(BaseAuditModel):
    """
    A possible answer option for a question (used for MULTIPLE_* types).
    """
    id_answer = models.AutoField(primary_key=True, db_column='id_answer')
    id_question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='id_question',
        related_name='answers',
    )
    answer_text = models.TextField(db_column='answer_text')
    is_correct = models.BooleanField(db_column='is_correct')

    class Meta:
        db_table = 'answer'
        verbose_name = 'Answer'
        verbose_name_plural = 'Answers'
        ordering = ['id_question', 'id_answer']

    def __str__(self):
        correct = "✓" if self.is_correct else "✗"
        return f"{correct} {self.answer_text[:50]}..."


class CodeQuestion(models.Model):
    """
    Extra data for CODE-type questions: language and JSON test cases / assertions.
    """
    question = models.OneToOneField(
        Question,
        on_delete=models.CASCADE,
        related_name='code_question',
        primary_key=True,
        db_column='id_question',
    )
    language = models.CharField(max_length=32, default='python', db_column='language')
    test_cases = models.JSONField(default=list, db_column='test_cases')

    class Meta:
        db_table = 'code_question'
        verbose_name = 'Code question'
        verbose_name_plural = 'Code questions'

    def __str__(self):
        return f"CodeQuestion({self.question_id})"
