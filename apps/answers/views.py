from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from loguru import logger
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.academic.permissions import IsStudent, IsTeacherOrAdmin
from apps.exams.models import ExamAssignment, ExamQuestion
from apps.questions.models import Answer, Question
from utils.responses import error_response, success_response

from .models import StudentAnswer
from .serializers import ManualGradeSerializer, StudentAnswerSerializer, SubmitExamSerializer
from .services import GradingService


def _get_role(request):
    role = getattr(request.user, 'role', None)
    if role is None and request.auth is not None:
        role = request.auth.get('role')
    return role


class SubmitExamAnswersView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = SubmitExamSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Datos invalidos.', serializer.errors)

        payload = serializer.validated_data
        assignment = (
            ExamAssignment.objects.select_related('exam', 'student')
            .filter(pk=payload['exam_assignment_id'])
            .first()
        )
        if not assignment:
            return error_response('Asignacion no encontrada.', status_code=status.HTTP_404_NOT_FOUND)

        if assignment.student_id != request.user.pk:
            return error_response('No tiene permiso para responder esta asignacion.', status_code=status.HTTP_403_FORBIDDEN)

        if assignment.status == 'completed':
            return error_response(
                'La asignacion ya fue completada y no permite reenvio.',
                status_code=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        if now < assignment.available_from or now > assignment.available_to:
            return error_response(
                'El examen no esta disponible en este momento.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        exam_question_ids = set(
            ExamQuestion.objects.filter(id_exam=assignment.exam)
            .values_list('id_question_id', flat=True)
        )
        if not exam_question_ids:
            return error_response('El examen no tiene preguntas configuradas.')

        submitted_question_ids = {item['question_id'] for item in payload['answers']}
        non_assigned_questions = submitted_question_ids - exam_question_ids
        if non_assigned_questions:
            return error_response(
                'Se enviaron preguntas que no pertenecen al examen.',
                {'question_ids': sorted(non_assigned_questions)},
            )

        existing_ids = set(
            StudentAnswer.objects.filter(
                exam_assignment=assignment,
                question_id__in=submitted_question_ids,
            ).values_list('question_id', flat=True)
        )
        if existing_ids:
            return error_response(
                'Ya existen respuestas registradas para algunas preguntas.',
                {'question_ids': sorted(existing_ids)},
                status_code=status.HTTP_409_CONFLICT,
            )

        questions = {
            q.id_question: q
            for q in (
                Question.objects.filter(id_question__in=submitted_question_ids)
                .prefetch_related('answers')
            )
        }

        answer_options_by_question = {
            question_id: {
                opt.id_answer: opt
                for opt in Answer.objects.filter(id_question_id=question_id)
            }
            for question_id in submitted_question_ids
        }

        prepared_answers = []
        for answer_payload in payload['answers']:
            question = questions.get(answer_payload['question_id'])
            if question is None:
                return error_response(
                    'Pregunta no encontrada.',
                    {'question_id': answer_payload['question_id']},
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            prepared = {
                'question': question,
                'selected_answer': None,
                'selected_answers': [],
                'answer_text': None,
                'code_answer': None,
            }

            if question.question_type == 'MULTIPLE_CHOICE':
                selected_answer_id = answer_payload.get('selected_answer')
                if selected_answer_id is None:
                    return error_response(
                        'La pregunta de opcion unica requiere selected_answer.',
                        {'question_id': question.id_question},
                    )
                selected_answer = answer_options_by_question[question.id_question].get(selected_answer_id)
                if selected_answer is None:
                    return error_response(
                        'La respuesta seleccionada no pertenece a la pregunta.',
                        {'question_id': question.id_question},
                    )
                prepared['selected_answer'] = selected_answer

            elif question.question_type == 'MULTIPLE_SELECTION':
                selected_answer_ids = answer_payload.get('selected_answers', [])
                if not selected_answer_ids:
                    return error_response(
                        'La pregunta de opcion multiple requiere selected_answers.',
                        {'question_id': question.id_question},
                    )
                unique_ids = list(set(selected_answer_ids))
                selected_options = [
                    answer_options_by_question[question.id_question].get(answer_id)
                    for answer_id in unique_ids
                ]
                if any(option is None for option in selected_options):
                    return error_response(
                        'Una o mas respuestas seleccionadas no pertenecen a la pregunta.',
                        {'question_id': question.id_question},
                    )
                prepared['selected_answers'] = selected_options

            elif question.question_type == 'OPEN':
                answer_text = answer_payload.get('answer_text', '').strip()
                if not answer_text:
                    return error_response(
                        'La pregunta abierta requiere answer_text.',
                        {'question_id': question.id_question},
                    )
                prepared['answer_text'] = answer_text

            elif question.question_type == 'CODE':
                code_answer = answer_payload.get('code_answer', '').strip()
                if not code_answer:
                    return error_response(
                        'La pregunta de codigo requiere code_answer.',
                        {'question_id': question.id_question},
                    )
                prepared['code_answer'] = code_answer

            else:
                return error_response(
                    'Tipo de pregunta no soportado.',
                    {'question_id': question.id_question, 'question_type': question.question_type},
                )

            prepared_answers.append(prepared)

        created_answers = []
        graded_details = []

        with transaction.atomic():
            for prepared in prepared_answers:
                question = prepared['question']
                student_answer = StudentAnswer(
                    exam_assignment=assignment,
                    question=question,
                    answer_text=prepared['answer_text'],
                    code_answer=prepared['code_answer'],
                    selected_answer=prepared['selected_answer'],
                )

                student_answer.save()

                if question.question_type == 'MULTIPLE_SELECTION':
                    student_answer.selected_answers.set(prepared['selected_answers'])

                grade_result = GradingService.grade_student_answer(student_answer)
                graded_details.append(
                    {
                        'question_id': question.id_question,
                        'graded': grade_result['graded'],
                        'is_correct': grade_result['is_correct'],
                        'score': grade_result['score'],
                        'feedback': grade_result.get('feedback', []),
                    }
                )
                created_answers.append(student_answer)

            answered_count = StudentAnswer.objects.filter(exam_assignment=assignment).count()
            total_questions = len(exam_question_ids)

            assignment.status = 'completed' if answered_count >= total_questions else 'in_progress'
            if assignment.attempt_date is None:
                assignment.attempt_date = now
            assignment.save(update_fields=['status', 'attempt_date', 'modified_at'])

            score_summary = None
            if assignment.status == 'completed':
                score_summary = GradingService.recalculate_assignment_score(assignment)

        logger.info(
            'Answers submitted | assignment={} student={} submitted={} status={}',
            assignment.pk,
            request.user.pk,
            len(created_answers),
            assignment.status,
        )

        return success_response(
            {
                'assignment_id': assignment.pk,
                'status': assignment.status,
                'submitted_count': len(created_answers),
                'total_questions': len(exam_question_ids),
                'score_summary': score_summary,
                'graded_answers': graded_details,
            },
            'Respuestas registradas exitosamente.',
            status.HTTP_201_CREATED,
        )


class ManualGradeAnswerView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]

    def post(self, request):
        serializer = ManualGradeSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Datos invalidos.', serializer.errors)

        payload = serializer.validated_data
        student_answer = (
            StudentAnswer.objects.select_related('exam_assignment', 'exam_assignment__exam', 'question')
            .filter(pk=payload['student_answer_id'])
            .first()
        )
        if not student_answer:
            return error_response('Respuesta del estudiante no encontrada.', status_code=status.HTTP_404_NOT_FOUND)

        role = _get_role(request)
        if role == 'teacher' and student_answer.exam_assignment.exam.id_teacher_id != request.user.pk:
            return error_response('No tiene permiso para calificar esta respuesta.', status_code=status.HTTP_403_FORBIDDEN)

        question_points = Decimal(student_answer.question.points)
        if payload['score'] > question_points:
            return error_response(
                'La calificacion no puede ser mayor al puntaje de la pregunta.',
                {'max_score': question_points},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        student_answer.score = payload['score']
        student_answer.is_correct = payload['is_correct']
        student_answer.evaluated_at = timezone.now()
        student_answer.save(update_fields=['score', 'is_correct', 'evaluated_at', 'modified_at'])

        assignment_summary = GradingService.recalculate_assignment_score(student_answer.exam_assignment)

        logger.info(
            'Manual grade applied | student_answer={} teacher={} score={} is_correct={}',
            student_answer.pk,
            request.user.pk,
            payload['score'],
            payload['is_correct'],
        )

        return success_response(
            {
                'student_answer': StudentAnswerSerializer(student_answer).data,
                'assignment_summary': assignment_summary,
            },
            'Calificacion manual aplicada exitosamente.',
        )


class AssignmentAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assignment_id: int):
        assignment = (
            ExamAssignment.objects.select_related('exam', 'student')
            .filter(pk=assignment_id)
            .first()
        )
        if not assignment:
            return error_response('Asignacion no encontrada.', status_code=status.HTTP_404_NOT_FOUND)

        role = _get_role(request)
        if role == 'student' and assignment.student_id != request.user.pk:
            return error_response('No tiene permiso para ver estas respuestas.', status_code=status.HTTP_403_FORBIDDEN)
        if role == 'teacher' and assignment.exam.id_teacher_id != request.user.pk:
            return error_response('No tiene permiso para ver estas respuestas.', status_code=status.HTTP_403_FORBIDDEN)
        if role not in ('student', 'teacher', 'admin'):
            return error_response('No tiene permiso para ver estas respuestas.', status_code=status.HTTP_403_FORBIDDEN)

        answers = (
            StudentAnswer.objects.filter(exam_assignment=assignment)
            .select_related('question', 'selected_answer')
            .prefetch_related('selected_answers', 'question__answers')
            .order_by('id_student_answer')
        )
        data = StudentAnswerSerializer(answers, many=True).data
        return success_response({'assignment_id': assignment.pk, 'answers': data})
