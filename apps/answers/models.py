from django.db import models

from apps.core.base_models import BaseAuditModel


class StudentAnswer(BaseAuditModel):
    id_student_answer = models.AutoField(primary_key=True, db_column='id_student_answer')
    exam_assignment = models.ForeignKey(
        'exams.ExamAssignment',
        on_delete=models.CASCADE,
        db_column='exam_assignment_id',
        related_name='student_answers',
    )
    question = models.ForeignKey(
        'questions.Question',
        on_delete=models.CASCADE,
        db_column='id_question',
        related_name='student_answers',
    )

    selected_answer = models.ForeignKey(
        'questions.Answer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='selected_answer_id',
        related_name='selected_in_student_answers',
    )
    selected_answers = models.ManyToManyField(
        'questions.Answer',
        related_name='multi_selected_in_student_answers',
        blank=True,
    )
    answer_text = models.TextField(null=True, blank=True, db_column='answer_text')
    code_answer = models.TextField(null=True, blank=True, db_column='code_answer')

    is_correct = models.BooleanField(null=True, blank=True, db_column='is_correct')
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        db_column='score',
    )
    evaluated_at = models.DateTimeField(null=True, blank=True, db_column='evaluated_at')

    class Meta:
        db_table = 'student_answer'
        verbose_name = 'Student Answer'
        verbose_name_plural = 'Student Answers'
        unique_together = [['exam_assignment', 'question']]
        ordering = ['-id_student_answer']

    def __str__(self):
        return (
            f'Answer {self.id_student_answer} | '
            f'Assignment {self.exam_assignment_id} | Question {self.question_id}'
        )
