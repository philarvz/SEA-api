from __future__ import annotations

import multiprocessing
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.exams.models import ExamQuestion
from apps.questions.models import CodeQuestion

from ..models import StudentAnswer

# Timeout in seconds for user code execution
_CODE_EXECUTION_TIMEOUT = 5
# Max code length accepted
_MAX_CODE_LENGTH = 10_000

# Patterns that indicate dangerous code
_DANGEROUS_IMPORT_RE = re.compile(
    r'(?:^|;|\s)(?:import|from)\s+'
    r'(?:os|sys|subprocess|shutil|socket|http|urllib|requests|ctypes|signal|'
    r'threading|multiprocessing|pickle|shelve|marshal|importlib|pkgutil|'
    r'code|codeop|compileall|asyncio|concurrent|webbrowser|pathlib|'
    r'tempfile|glob|fnmatch|io|builtins)\b',
    re.MULTILINE,
)
_DANGEROUS_ATTR_RE = re.compile(
    r'__(?:import|builtins|class|subclasses|bases|mro|loader|spec)__'
    r'|(?:^|[^a-zA-Z_])(?:exec|eval|compile|globals|locals|vars|dir'
    r'|getattr|setattr|delattr|breakpoint)\s*\(',
    re.MULTILINE,
)
_OPEN_CALL_RE = re.compile(r'\bopen\s*\(', re.MULTILINE)


class GradingService:
    SCORE_SCALE = Decimal('10.00')
    _SAFE_BUILTINS = {
        'abs': abs,
        'all': all,
        'any': any,
        'bool': bool,
        'dict': dict,
        'enumerate': enumerate,
        'float': float,
        'int': int,
        'len': len,
        'list': list,
        'max': max,
        'min': min,
        'pow': pow,
        'print': print,
        'range': range,
        'round': round,
        'set': set,
        'str': str,
        'sum': sum,
        'tuple': tuple,
        'zip': zip,
    }

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

            passed, feedback = GradingService._run_code_test_cases(
                student_answer.code_answer or '',
                code_question.test_cases,
            )
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

    @staticmethod
    def _validate_code_safety(code: str) -> list[str]:
        """Pre-validate code for dangerous patterns. Returns list of issues."""
        issues = []
        if len(code) > _MAX_CODE_LENGTH:
            issues.append(f'El código excede el límite de {_MAX_CODE_LENGTH} caracteres.')
            return issues

        if _DANGEROUS_IMPORT_RE.search(code):
            issues.append('El código contiene imports no permitidos.')
        if _DANGEROUS_ATTR_RE.search(code):
            issues.append('El código contiene patrones no permitidos.')
        if _OPEN_CALL_RE.search(code):
            issues.append('El código contiene llamadas a open() no permitidas.')
        return issues

    @staticmethod
    def _execute_user_code(code_answer: str, namespace: dict) -> str | None:
        """Executes user code in the sandbox namespace. Returns an error message or None."""
        try:
            exec(code_answer, namespace, namespace)  # NOSONAR — sandboxed exec, pre-validated
            return None
        except Exception as exc:
            return f'Error de ejecucion del codigo: {exc}'

    @staticmethod
    def _is_function_test_case(test_case: dict) -> bool:
        return 'function_name' in test_case and 'input' in test_case and 'expected_output' in test_case

    @staticmethod
    def _call_function_test(test_case: dict, namespace: dict) -> None:
        """Invokes a named function from namespace and asserts the expected output."""
        fn = namespace.get(test_case['function_name'])
        if not callable(fn):
            raise AssertionError('La funcion objetivo no existe o no es invocable.')
        raw_input = test_case['input']
        if isinstance(raw_input, list):
            result = fn(*raw_input)
        elif isinstance(raw_input, dict):
            result = fn(**raw_input)
        else:
            result = fn(raw_input)
        if result != test_case['expected_output']:
            raise AssertionError(f"Esperado {test_case['expected_output']}, obtenido {result}")

    @staticmethod
    def _run_dict_test_case(test_case: dict, namespace: dict) -> None:
        """Handles a dict-style test case. Raises AssertionError on failure."""
        if 'assertion' in test_case:
            exec(test_case['assertion'], namespace, namespace)
        elif 'expression' in test_case and 'expected_output' in test_case:
            result = eval(test_case['expression'], namespace, namespace)
            if result != test_case['expected_output']:
                raise AssertionError(f"Esperado {test_case['expected_output']}, obtenido {result}")
        elif GradingService._is_function_test_case(test_case):
            GradingService._call_function_test(test_case, namespace)
        else:
            raise AssertionError('Formato de caso de prueba no soportado.')

    @staticmethod
    def _run_single_test(test_case: Any, namespace: dict) -> None:
        """Dispatches a single test case by type. Raises AssertionError or Exception on failure."""
        if isinstance(test_case, str):
            exec(test_case, namespace, namespace)
        elif isinstance(test_case, dict):
            GradingService._run_dict_test_case(test_case, namespace)
        else:
            raise AssertionError('Formato de caso de prueba no soportado.')

    @staticmethod
    def _run_code_test_cases(code_answer: str, test_cases: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
        # --- Pre-validation: reject dangerous code before execution ---
        safety_issues = GradingService._validate_code_safety(code_answer)
        if safety_issues:
            return False, [{'test_case': 0, 'error': '; '.join(safety_issues)}]

        namespace: dict = {'__builtins__': GradingService._SAFE_BUILTINS}
        feedback: list[dict[str, Any]] = []

        # --- Execute user code with timeout via multiprocessing ---
        result_queue: multiprocessing.Queue = multiprocessing.Queue()

        def _target(q: multiprocessing.Queue) -> None:
            try:
                exec(code_answer, namespace, namespace)  # NOSONAR — sandboxed
                q.put(('ok', None, namespace))
            except Exception as exc:
                q.put(('error', str(exc), None))

        proc = multiprocessing.Process(target=_target, args=(result_queue,), daemon=True)
        proc.start()
        proc.join(timeout=_CODE_EXECUTION_TIMEOUT)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
            return False, [{'test_case': 0, 'error': f'El código excedió el tiempo límite de {_CODE_EXECUTION_TIMEOUT} segundos.'}]

        if result_queue.empty():
            return False, [{'test_case': 0, 'error': 'Error de ejecución del código.'}]

        status_val, msg, _ = result_queue.get_nowait()
        if status_val == 'error':
            return False, [{'test_case': 0, 'error': f'Error de ejecucion del codigo: {msg}'}]

        # Merge executed namespace back — multiprocessing can't share complex objects,
        # so for test_cases we re-exec in the main thread since code is already validated.
        # The timeout protects against infinite loops; after passing that, re-exec is safe.
        error = GradingService._execute_user_code(code_answer, namespace)
        if error:
            return False, [{'test_case': 0, 'error': error}]

        all_passed = True
        for index, test_case in enumerate(test_cases, start=1):
            try:
                GradingService._run_single_test(test_case, namespace)
                feedback.append({'test_case': index, 'status': 'passed'})
            except AssertionError as exc:
                all_passed = False
                feedback.append({'test_case': index, 'status': 'failed', 'error': str(exc)})
            except Exception as exc:
                all_passed = False
                feedback.append({'test_case': index, 'status': 'error', 'error': str(exc)})

        return all_passed, feedback
