"""
Exams module service layer.
Encapsulates business logic for exam CRUD operations.
"""

from loguru import logger
from django.utils import timezone
from django.db.models import Q

from .models import Exam
from apps.academic.models import Subject
from apps.users.models import User


class ExamService:
    """Business logic for Exam management."""

    @staticmethod
    def create_exam(validated_data: dict, token_user) -> Exam:
        """
        Create a new exam with the given validated data.
        token_user may be a simplejwt TokenUser; resolve to a real User instance.
        """
        teacher = User.objects.get(pk=token_user.pk)
        subject = Subject.objects.get(pk=validated_data['id_subject'])

        exam = Exam(
            name=validated_data['name'],
            title=validated_data['name'],
            id_subject=subject,
            id_teacher=teacher,
            unit_number=validated_data['unit_number'],
            difficulty_level=validated_data['difficulty_level'],
            secure_mode=validated_data.get('secure_mode', False),
            creation_date=timezone.now().date(),
            status=True,
        )
        exam.save()

        logger.info(
            'Exam created | id={} name={} subject={} teacher={}',
            exam.pk, exam.name, subject.pk, teacher.pk,
        )
        return exam

    @staticmethod
    def update_exam(exam: Exam, validated_data: dict) -> Exam:
        """
        Update an existing exam with the validated data.
        """
        subject = Subject.objects.get(pk=validated_data['id_subject'])

        exam.name = validated_data['name']
        exam.title = validated_data['name']
        exam.id_subject = subject
        exam.unit_number = validated_data['unit_number']
        exam.difficulty_level = validated_data['difficulty_level']
        exam.secure_mode = validated_data['secure_mode']
        exam.status = validated_data['status']
        exam.save()

        logger.info('Exam updated | id={}', exam.pk)
        return exam

    @staticmethod
    def change_status(exam: Exam, new_status: bool) -> Exam:
        """Toggle the active/inactive status of an exam."""
        exam.status = new_status
        exam.save(update_fields=['status', 'updated_at'])
        state = 'activado' if new_status else 'desactivado'
        logger.info('Exam {} | id={}', state, exam.pk)
        return exam

    @staticmethod
    def soft_delete(exam: Exam) -> Exam:
        """Logically delete an exam by setting status=False."""
        exam.status = False
        exam.save(update_fields=['status', 'updated_at'])
        logger.info('Exam soft-deleted | id={}', exam.pk)
        return exam

    @staticmethod
    def get_filtered_queryset(params: dict, user):
        """
        Build qualified queryset based on query parameters and user role.
        Teachers only see their own exams.
        """
        queryset = Exam.objects.select_related(
            'id_subject', 'id_teacher'
        ).all()

        # Teacher can only see own exams — compare by pk to avoid TokenUser vs User mismatch
        role = getattr(user, 'role', None)
        if role is None:
            role = getattr(user, 'auth', {}).get('role') if hasattr(user, 'auth') else None
        if role == 'teacher':
            queryset = queryset.filter(id_teacher_id=user.pk)

        # Optional filters
        status_param = params.get('status')
        if status_param is not None:
            queryset = queryset.filter(status=status_param.lower() in ('true', '1'))

        subject_id = params.get('id_subject')
        if subject_id:
            queryset = queryset.filter(id_subject_id=subject_id)

        difficulty = params.get('difficulty_level')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(id_subject__name__icontains=search)
            )

        return queryset
