"""
Grading service for the answers module.

CODE-type questions are evaluated asynchronously via a Celery task that runs
student code inside an isolated Docker container.  No ``exec()`` or ``eval()``
of student code happens in the Django / Celery worker process.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from loguru import logger

from apps.exams.models import ExamQuestion
from apps.questions.models import CodeQuestion

from ..models import StudentAnswer


# Timeout (seconds) to wait for the Celery sandbox task to finish.
_CELERY_RESULT_TIMEOUT = int(getattr(settings, 'SANDBOX_TIMEOUT_SECONDS', 10)) + 15


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
    # CODE grading — delegates to the Docker-based Celery sandbox
    # ------------------------------------------------------------------

    @staticmethod
    def _grade_code_answer(student_answer: StudentAnswer, question) -> dict[str, Any]:
        """Grade a CODE answer by dispatching a Celery task that runs the
        student code inside an isolated Docker container.

        The previous implementation used ``exec()`` directly in the Django
        process, which is a critical security vulnerability (CWE-94).  This
        version never executes untrusted code in-process.
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

        # Import here to avoid circular imports at module level.
        from apps.answers.tasks import run_code_in_sandbox

        code = student_answer.code_answer or ''
        test_cases = code_question.test_cases or []

        # Dispatch to sandboxed Docker container via Celery and wait for the result.
        try:
            async_result = run_code_in_sandbox.delay(code, test_cases)
            sandbox_result = async_result.get(timeout=_CELERY_RESULT_TIMEOUT)
        except Exception as exc:
            logger.error(
                'Sandbox task failed | answer={} error={}',
                student_answer.pk,
                exc,
            )
            # Mark as not graded so it can be retried or manually reviewed.
            return {
                'graded': False,
                'is_correct': None,
                'score': None,
                'feedback': ['Error interno al evaluar el codigo. Intente nuevamente.'],
            }

        # Translate the sandbox result into feedback compatible with existing API.
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
