"""
Exams module service layer.
Encapsulates business logic for exam CRUD operations.
"""

from loguru import logger
from django.utils import timezone
from django.db.models import Q

from .models import Exam, ExamAssignment
from apps.academic.models import Subject
from apps.users.models import User, StudentProfile


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


class ExamAssignmentService:
    """Business logic for bulk exam-to-group assignments."""

    @staticmethod
    def assign_exam_to_groups(
        exam, groups, available_from, available_to, teacher_pk,
    ) -> dict:
        """
        Assign *exam* to every active student in the given *groups*.

        Returns a summary dict:
            total_students  – active students found across all groups
            created         – new ExamAssignment records inserted
            skipped         – duplicates that already existed
        """
        now = timezone.now()

        # Collect active students per group
        # StudentProfile.group is a FK to Group; the student's User must be active.
        student_profiles = StudentProfile.objects.filter(
            group__in=groups,
            user__is_active=True,
            user__status=True,
            user__role='student',
        ).select_related('user', 'group')

        # Build list of (student_user_id, group_id)
        student_group_pairs = [
            (sp.user_id, sp.group_id) for sp in student_profiles
        ]

        total_students = len(student_group_pairs)

        if total_students == 0:
            logger.info(
                'Exam assignment skipped — no active students | exam={} groups={}',
                exam.pk, [g.pk for g in groups],
            )
            return {'total_students': 0, 'created': 0, 'skipped': 0}

        # Detect existing assignments to avoid duplicates
        existing_pairs = set(
            ExamAssignment.objects.filter(
                exam=exam,
                student_id__in=[uid for uid, _ in student_group_pairs],
            ).values_list('student_id', flat=True)
        )

        new_assignments = []
        skipped = 0

        for student_id, group_id in student_group_pairs:
            if student_id in existing_pairs:
                skipped += 1
                continue

            new_assignments.append(ExamAssignment(
                exam=exam,
                student_id=student_id,
                group_id=group_id,
                status='pending',
                score=None,
                is_passed=None,
                assigned_at=now,
                available_from=available_from,
                available_to=available_to,
                attempt_date=None,
            ))
            # Mark as seen so intra-batch duplicates (same student in
            # two groups) are also handled.
            existing_pairs.add(student_id)

        if new_assignments:
            ExamAssignment.objects.bulk_create(new_assignments)

        created = len(new_assignments)

        logger.info(
            'Exam assigned | exam={} groups={} total={} created={} skipped={} teacher={}',
            exam.pk, [g.pk for g in groups], total_students, created, skipped, teacher_pk,
        )

        return {
            'total_students': total_students,
            'created': created,
            'skipped': skipped,
        }
