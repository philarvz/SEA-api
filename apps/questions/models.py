"""
Questions module models
Includes: Question, Answer
"""

from django.db import models


class Question(models.Model):
    """
    Model representing an exam question
    """
    BLOOM_LEVEL_CHOICES = [
        ('remember', 'Remember'),
        ('understand', 'Understand'),
        ('apply', 'Apply'),
        ('analyze', 'Analyze'),
        ('evaluate', 'Evaluate'),
        ('create', 'Create'),
    ]

    id_question = models.AutoField(primary_key=True, db_column='id_question')
    id_subject = models.ForeignKey(
        'academic.Subject',
        on_delete=models.CASCADE,
        db_column='id_subject',
        related_name='questions'
    )
    statement = models.TextField()
    bloom_level = models.CharField(
        max_length=50,
        choices=BLOOM_LEVEL_CHOICES,
        db_column='bloom_level'
    )
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'question'
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['id_subject', 'id_question']

    def __str__(self):
        return f"Question {self.id_question}: {self.statement[:50]}..."


class Answer(models.Model):
    """
    Model representing a possible answer for a question
    """
    id_answer = models.AutoField(primary_key=True, db_column='id_answer')
    id_question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='id_question',
        related_name='answers'
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
