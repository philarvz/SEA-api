"""
Exams module service layer.
Encapsulates business logic for exam CRUD operations.
"""

from loguru import logger
from django.utils import timezone
from django.db.models import Q

from .models import Exam, ExamAssignment, ExamGroupAssignment, ExamQuestion
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
            minimum_score=validated_data.get('minimum_score', 8),
            creation_date=timezone.now(),
            status=False,
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
        exam.minimum_score = validated_data['minimum_score']
        exam.status = validated_data['status']
        exam.save()

        logger.info('Exam updated | id={}', exam.pk)
        return exam

    @staticmethod
    def sync_exam_questions(exam: Exam, question_ids: list[int]) -> None:
        """
        Reemplaza los vínculos examen–pregunta. El orden del array solo determina
        el orden estable de creación (id_exam_question); no es el orden de presentación
        al alumno (eso se define al tomar el examen, p. ej. aleatorio).

        Cada pregunta debe ser de la misma materia que el examen.
        """
        from django.db import transaction
        from apps.questions.models import Question

        seen: set[int] = set()
        ordered_unique: list[int] = []
        for qid in question_ids:
            if qid in seen:
                raise ValueError('La lista de preguntas contiene duplicados.')
            seen.add(qid)
            ordered_unique.append(qid)

        with transaction.atomic():
            ExamQuestion.objects.filter(id_exam=exam).delete()
            for qid in ordered_unique:
                try:
                    q = Question.objects.get(pk=qid)
                except Question.DoesNotExist:
                    raise ValueError(f'La pregunta con id {qid} no existe.')
                if q.id_subject_id != exam.id_subject_id:
                    raise ValueError(
                        f'La pregunta {qid} es de otra materia; el examen pertenece a la materia '
                        f'{exam.id_subject_id} ({exam.id_subject.name}).'
                    )
                ExamQuestion.objects.create(
                    id_exam=exam,
                    id_question_id=qid,
                )

        logger.info(
            'Exam questions synced | exam={} count={}',
            exam.pk, len(ordered_unique),
        )

    @staticmethod
    def validate_can_activate(exam: Exam) -> list:
        """
        Returns a list of human-readable error messages for every condition
        that prevents activation.  An empty list means the exam can be activated.

        An exam can only be set to active when:
          1. It has at least one question.
          2. It has at least one group assigned.
          3. At least one group assignment window has not yet expired.
        """
        errors = []
        now = timezone.now()

        if not exam.exam_questions.exists():
            errors.append('El examen debe tener al menos una pregunta asignada.')

        has_groups = exam.group_assignments.exists()
        if not has_groups:
            errors.append('El examen debe tener al menos un grupo asignado.')
        elif not exam.group_assignments.filter(available_to__gte=now).exists():
            errors.append(
                'Todos los períodos de disponibilidad han expirado. '
                'Reasigna los grupos con fechas válidas antes de activar el examen.'
            )

        return errors

    @staticmethod
    def change_status(exam: Exam, new_status: bool) -> Exam:
        """Toggle the active/inactive status of an exam."""
        exam.status = new_status
        exam.save(update_fields=['status', 'modified_at'])
        state = 'activado' if new_status else 'desactivado'
        logger.info('Exam {} | id={}', state, exam.pk)
        return exam

    @staticmethod
    def change_secure_mode(exam: Exam, secure_mode: bool) -> Exam:
        """Activate or deactivate secure mode for an exam."""
        exam.secure_mode = secure_mode
        exam.save(update_fields=['secure_mode', 'modified_at'])
        state = 'activado' if secure_mode else 'desactivado'
        logger.info('Exam secure_mode {} | id={}', state, exam.pk)
        return exam

    @staticmethod
    def soft_delete(exam: Exam) -> Exam:
        """Logically delete an exam by setting status=False."""
        exam.status = False
        exam.save(update_fields=['status', 'modified_at'])
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

    @staticmethod
    def get_exams_created_by(user_pk, params: dict):
        """
        Return paginated-ready queryset of exams created by the given user.
        Applies the additional safety filter that the creator must be a
        teacher or admin (double check against DB role, not just token).
        Uses prefetch_related to resolve unit_name without N+1 queries.
        Expects params already validated by CreatedByMeQuerySerializer.
        """
        queryset = Exam.objects.select_related(
            'id_subject', 'id_teacher',
        ).prefetch_related(
            'id_subject__units',
        ).filter(
            id_teacher_id=user_pk,
            id_teacher__role__in=('teacher', 'admin'),
        )

        # Optional: filter by active/inactive status (validated bool or None)
        status_param = params.get('status')
        if status_param is not None:
            queryset = queryset.filter(status=status_param)

        # Optional: filter by subject
        subject_id = params.get('id_subject')
        if subject_id is not None:
            queryset = queryset.filter(id_subject_id=subject_id)

        # Optional: filter by difficulty
        difficulty = params.get('difficulty_level')
        if difficulty is not None:
            queryset = queryset.filter(difficulty_level=difficulty)

        # Optional: full-text search over name and subject name
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(id_subject__name__icontains=search)
            )

        return queryset


class ExamAssignmentService:
    """Business logic for bulk exam-to-group assignments."""

    @staticmethod
    def sync_exam_groups(
        exam, groups, available_from, available_to, teacher_pk,
    ) -> dict:
        """
        Synchronise exam assignments so they match exactly the given *groups*.

        Group-level intent is stored in ExamGroupAssignment (persists even for
        groups with zero students).  Per-student records live in ExamAssignment.

        - New groups → upsert ExamGroupAssignment + bulk_create student ExamAssignments
        - Removed groups → delete ExamGroupAssignment + delete pending ExamAssignments
        - Kept groups → update window on ExamGroupAssignment + pending ExamAssignments
        """
        from django.db import transaction

        now = timezone.now()
        new_group_ids = {g.pk for g in groups}

        with transaction.atomic():
            # --- 1. Group-level: determine previous state -----------------------
            existing_group_ids = set(
                ExamGroupAssignment.objects.filter(exam=exam)
                .values_list('group_id', flat=True)
            )

            removed_group_ids = existing_group_ids - new_group_ids
            added_group_ids   = new_group_ids - existing_group_ids
            kept_group_ids    = existing_group_ids & new_group_ids

            # --- 2. Remove groups -----------------------------------------------
            removed_students = 0
            if removed_group_ids:
                ExamGroupAssignment.objects.filter(
                    exam=exam, group_id__in=removed_group_ids,
                ).delete()
                removed_students = ExamAssignment.objects.filter(
                    exam=exam,
                    group_id__in=removed_group_ids,
                    status='pending',
                ).delete()[0]

            # --- 3. Add new groups -----------------------------------------------
            created_students = 0
            if added_group_ids:
                added_groups = [g for g in groups if g.pk in added_group_ids]

                # Upsert group-level records
                for gid in added_group_ids:
                    ExamGroupAssignment.objects.update_or_create(
                        exam=exam, group_id=gid,
                        defaults={
                            'available_from': available_from,
                            'available_to': available_to,
                        },
                    )

                # Create student-level assignments for active students
                student_profiles = StudentProfile.objects.filter(
                    group__in=added_groups,
                    user__is_active=True,
                    user__status=True,
                    user__role='student',
                ).select_related('user', 'group')

                seen_students: set = set()
                new_assignments = []
                for sp in student_profiles:
                    if sp.user_id in seen_students:
                        continue
                    seen_students.add(sp.user_id)
                    new_assignments.append(ExamAssignment(
                        exam=exam,
                        student_id=sp.user_id,
                        group_id=sp.group_id,
                        status='pending',
                        score=None,
                        is_passed=None,
                        assigned_at=now,
                        available_from=available_from,
                        available_to=available_to,
                        attempt_date=None,
                    ))

                if new_assignments:
                    ExamAssignment.objects.bulk_create(new_assignments)
                    created_students = len(new_assignments)

            # --- 4. Update window for kept groups --------------------------------
            updated_students = 0
            if kept_group_ids:
                ExamGroupAssignment.objects.filter(
                    exam=exam, group_id__in=kept_group_ids,
                ).update(available_from=available_from, available_to=available_to)

                updated_students = ExamAssignment.objects.filter(
                    exam=exam,
                    group_id__in=kept_group_ids,
                    status='pending',
                ).update(available_from=available_from, available_to=available_to)

        logger.info(
            'Exam groups synced | exam={} groups={} created={} removed={} updated={} teacher={}',
            exam.pk, sorted(new_group_ids), created_students,
            removed_students, updated_students, teacher_pk,
        )

        return {
            'created': created_students,
            'removed': removed_students,
            'updated': updated_students,
        }

    @staticmethod
    def get_assigned_groups(exam) -> list:
        """
        Return a summary of which groups an exam is assigned to.
        Reads from ExamGroupAssignment so groups with zero students are included.
        """
        from django.db.models import Count

        rows = (
            ExamGroupAssignment.objects
            .filter(exam=exam)
            .select_related('group', 'group__id_generation')
            .annotate(
                students_assigned=Count(
                    'group__exam_assignments',
                    filter=Q(group__exam_assignments__exam=exam),
                )
            )
            .order_by('group_id')
        )

        result = []
        for row in rows:
            gen = row.group.id_generation
            gen_year = gen.year if gen else ''
            letter = row.group.group_letter
            result.append({
                'group_id': row.group_id,
                'group_label': f"{letter} (Gen {gen_year})",
                'academic_level': row.group.academic_level,
                'students_assigned': row.students_assigned,
                'available_from': row.available_from,
                'available_to': row.available_to,
            })
        return result

    @staticmethod
    def get_group_stats(exam, group_id: int | None = None) -> list:
        """
        Return per-group statistics for an exam.
        If group_id is given, returns only that group's stats (one-element list).
        Groups come from ExamGroupAssignment so groups with 0 students appear.
        Aggregations are done at DB level via a single query on ExamAssignment.
        """
        from django.db.models import Avg, Count, Max, Min
        from decimal import Decimal

        minimum = exam.minimum_score

        # --- 1. Aggregate student stats per group in one query ----------------
        assignment_qs = ExamAssignment.objects.filter(exam=exam)
        if group_id is not None:
            assignment_qs = assignment_qs.filter(group_id=group_id)

        agg_rows = (
            assignment_qs
            .values('group_id')
            .annotate(
                total_students=Count('id_assignment'),
                average_score=Avg('score'),
                highest_score=Max('score'),
                lowest_score=Min('score'),
                pending_count=Count('id_assignment', filter=Q(status='pending')),
                in_progress_count=Count('id_assignment', filter=Q(status='in_progress')),
                completed_count=Count('id_assignment', filter=Q(status='completed')),
                approved_count=Count(
                    'id_assignment',
                    filter=Q(score__gte=minimum, score__isnull=False),
                ),
                scored_count=Count(
                    'id_assignment',
                    filter=Q(score__isnull=False),
                ),
            )
        )
        stats_by_group = {row['group_id']: row for row in agg_rows}

        # --- 2. List assigned groups (filtered if group_id supplied) ----------
        group_qs = ExamGroupAssignment.objects.filter(exam=exam)
        if group_id is not None:
            group_qs = group_qs.filter(group_id=group_id)

        group_rows = (
            group_qs
            .select_related('group', 'group__id_generation')
            .order_by('group_id')
        )

        result = []
        for ga in group_rows:
            grp = ga.group
            gen = grp.id_generation
            gen_year = gen.year if gen else ''
            label = f"{grp.academic_level}{grp.group_letter} (Gen {gen_year})"

            agg = stats_by_group.get(ga.group_id)
            if agg:
                scored = agg['scored_count']
                approval_rate = (
                    round(Decimal(agg['approved_count']) / Decimal(scored) * 100, 2)
                    if scored > 0 else None
                )
                avg_score = round(agg['average_score'], 2) if agg['average_score'] is not None else None
                result.append({
                    'group_id': ga.group_id,
                    'group_label': label,
                    'total_students': agg['total_students'],
                    'average_score': avg_score,
                    'highest_score': agg['highest_score'],
                    'lowest_score': agg['lowest_score'],
                    'approval_rate': approval_rate,
                    'pending_count': agg['pending_count'],
                    'in_progress_count': agg['in_progress_count'],
                    'completed_count': agg['completed_count'],
                })
            else:
                result.append({
                    'group_id': ga.group_id,
                    'group_label': label,
                    'total_students': 0,
                    'average_score': None,
                    'highest_score': None,
                    'lowest_score': None,
                    'approval_rate': None,
                    'pending_count': 0,
                    'in_progress_count': 0,
                    'completed_count': 0,
                })

        return result

    @staticmethod
    def get_group_students(
        exam,
        group_id: int,
        status_filter: str | None = None,
        search: str | None = None,
    ):
        """
        Return ExamAssignment queryset for a specific exam + group,
        ordered by last_name, first_name for the grades view.
        Uses select_related to resolve student data in a single query.
        Optional status_filter: 'pending' | 'in_progress' | 'completed'.
        Optional search: case-insensitive match on first_name, last_name, or matricula.
        """
        qs = (
            ExamAssignment.objects
            .filter(exam=exam, group_id=group_id)
            .select_related('student')
            .order_by('student__last_name', 'student__first_name')
        )
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__matricula__icontains=search)
            )
        return qs

    @staticmethod
    def get_student_assignments(student_pk, params: dict):
        """
        Return queryset of assignments for a single student.
        Optimised with select_related to avoid N+1.
        Optional filters: status (str|None), include_completed (bool).
        Expects params already validated by MyAssignmentQuerySerializer.
        """
        queryset = ExamAssignment.objects.select_related(
            'exam', 'exam__id_subject', 'group', 'group__id_generation',
        ).filter(
            student_id=student_pk,
            exam__status=True,          # only active exams
        )

        # include_completed is a validated bool (default False) from the serializer
        include_completed = params.get('include_completed', False)
        if not include_completed:
            queryset = queryset.exclude(status='completed')

        # status is a validated ChoiceField value (or None)
        status_param = params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset
