"""
Grading service for the answers module.

CODE-type questions are evaluated synchronously via a Docker sandbox
container.  No ``exec()`` or ``eval()`` of student code happens in
the Django process.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Sum
from django.utils import timezone
from loguru import logger

from apps.exams.models import ExamQuestion
from apps.questions.models import CodeQuestion

from ..models import StudentAnswer
from .code_execution_service import run_code_in_sandbox


class GradingService:
    SCORE_SCALE = Decimal('10.00')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def grade_student_answer(student_answer: StudentAnswer) -> dict[str, Any]:
        question = student_answer.question
        question_type = question.question_type

        if question_type == 'OPEN':
            return {
                'graded': False,
                'is_correct': None,
                'score': None,
                'feedback': ['Pregunta abierta pendiente de evaluacion manual.'],
            }

        if question_type == 'MULTIPLE_CHOICE':
            is_correct = bool(
                student_answer.selected_answer and student_answer.selected_answer.is_correct
            )
            score = Decimal(question.points if is_correct else 0)
            student_answer.is_correct = is_correct
            student_answer.score = score
            student_answer.evaluated_at = timezone.now()
            student_answer.save(update_fields=['is_correct', 'score', 'evaluated_at', 'modified_at'])
            return {
                'graded': True,
                'is_correct': is_correct,
                'score': score,
                'feedback': [],
            }

        if question_type == 'MULTIPLE_SELECTION':
            selected_ids = set(
                student_answer.selected_answers.values_list('id_answer', flat=True)
            )
            correct_ids = set(
                question.answers.filter(is_correct=True).values_list('id_answer', flat=True)
            )
            is_correct = selected_ids == correct_ids
            score = Decimal(question.points if is_correct else 0)
            student_answer.is_correct = is_correct
            student_answer.score = score
            student_answer.evaluated_at = timezone.now()
            student_answer.save(update_fields=['is_correct', 'score', 'evaluated_at', 'modified_at'])
            return {
                'graded': True,
                'is_correct': is_correct,
                'score': score,
                'feedback': [],
            }

        if question_type == 'CODE':
            return GradingService._grade_code_answer(student_answer, question)

        return {
            'graded': False,
            'is_correct': None,
            'score': None,
            'feedback': ['Tipo de pregunta no soportado para evaluacion automatica.'],
        }

    @staticmethod
    def recalculate_assignment_score(exam_assignment) -> dict[str, Any]:
        total_points = (
            ExamQuestion.objects.filter(id_exam=exam_assignment.exam)
            .aggregate(total=Sum('id_question__points'))
            .get('total')
            or 0
        )

        answered_total = (
            StudentAnswer.objects.filter(exam_assignment=exam_assignment)
            .aggregate(total=Sum('score'))
            .get('total')
            or Decimal('0.00')
        )

        if total_points <= 0:
            normalized_score = Decimal('0.00')
        else:
            normalized_score = (
                (Decimal(answered_total) / Decimal(total_points)) * GradingService.SCORE_SCALE
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        exam_assignment.score = normalized_score
        exam_assignment.is_passed = normalized_score >= exam_assignment.exam.minimum_score
        exam_assignment.status = 'completed'
        if exam_assignment.attempt_date is None:
            exam_assignment.attempt_date = timezone.now()
        exam_assignment.save(
            update_fields=['score', 'is_passed', 'status', 'attempt_date', 'modified_at']
        )

        return {
            'score': normalized_score,
            'is_passed': exam_assignment.is_passed,
            'status': exam_assignment.status,
        }

    # ------------------------------------------------------------------
    # CODE grading — synchronous Docker sandbox execution
    # ------------------------------------------------------------------

    @staticmethod
    def _grade_code_answer(student_answer: StudentAnswer, question) -> dict[str, Any]:
        """Grade a CODE answer by running student code inside an isolated
        Docker container via ``subprocess.run``.

        The call is synchronous — no Celery broker or worker needed.
        Student code is NEVER executed in-process (no ``exec``/``eval``).
        """
        code_question = CodeQuestion.objects.filter(question=question).first()
        if not code_question:
            student_answer.is_correct = False
            student_answer.score = Decimal('0.00')
            student_answer.evaluated_at = timezone.now()
            student_answer.save(update_fields=['is_correct', 'score', 'evaluated_at', 'modified_at'])
            return {
                'graded': True,
                'is_correct': False,
                'score': Decimal('0.00'),
                'feedback': ['La pregunta de codigo no tiene casos de prueba configurados.'],
            }

        code = student_answer.code_answer or ''
        test_cases = code_question.test_cases or []

        # Execute inside Docker sandbox (synchronous, blocks until done).
        sandbox_result = run_code_in_sandbox(code, test_cases)

        # Translate the sandbox result into feedback compatible with the API.
        passed = sandbox_result.get('passed', False)
        sandbox_error = sandbox_result.get('error')
        raw_results = sandbox_result.get('results', [])

        feedback: list[dict[str, Any]] = []
        if sandbox_error:
            feedback.append({'test_case': 0, 'status': 'error', 'error': sandbox_error})

        for idx, tc_result in enumerate(raw_results, start=1):
            if tc_result.get('passed'):
                feedback.append({'test_case': idx, 'status': 'passed'})
            else:
                err = tc_result.get('error', f"Esperado {tc_result.get('expected')}, obtenido {tc_result.get('output')}")
                feedback.append({'test_case': idx, 'status': 'failed', 'error': err})

        score = Decimal(question.points if passed else 0)
        student_answer.is_correct = passed
        student_answer.score = score
        student_answer.evaluated_at = timezone.now()
        student_answer.save(update_fields=['is_correct', 'score', 'evaluated_at', 'modified_at'])

        return {
            'graded': True,
            'is_correct': passed,
            'score': score,
            'feedback': feedback,
        }
