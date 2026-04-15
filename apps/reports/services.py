from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Max, Min

from apps.exams.models import Exam, ExamAssignment, ExamGroupAssignment
from apps.academic.models import Group, GroupTeacherAssignment
from apps.users.models import TeacherProfile


class ReportService:

    # ===== HELPERS =====

    @staticmethod
    def _map_status(status: str) -> str:
        return {
            "completed": "finished",
            "pending": "pending",
            "in_progress": "in_progress",
        }.get(status, status)

    @staticmethod
    def _calculate_summary_metrics(qs):
        total_exams = qs.count()

        # ExamAssignment-based reports should count unique students, not rows.
        if hasattr(qs.model, 'student_id'):
            total_students = qs.values('student_id').distinct().count()
        else:
            total_students = total_exams

        avg = qs.aggregate(avg=Avg('score'))['avg'] or 0
        highest = qs.aggregate(max=Max('score'))['max']
        lowest = qs.aggregate(min=Min('score'))['min']
        approved = qs.filter(score__gte=70).count()

        return {
            "totalStudents": total_students,
            "totalExams": total_exams,
            "averageGrade": avg,
            "approvalRate": (approved / total_exams * 100) if total_exams else 0,
            "highestGrade": highest,
            "lowestGrade": lowest,
        }

    @staticmethod
    def _calculate_distribution(qs):
        total = qs.count() or 1

        ranges = [
            ("0-59", qs.filter(score__lt=60).count()),
            ("60-69", qs.filter(score__gte=60, score__lt=70).count()),
            ("70-79", qs.filter(score__gte=70, score__lt=80).count()),
            ("80-89", qs.filter(score__gte=80, score__lt=90).count()),
            ("90-100", qs.filter(score__gte=90).count()),
        ]

        return [
            {
                "range": r[0],
                "count": r[1],
                "percentage": (r[1] / total) * 100,
            }
            for r in ranges
        ]

    @staticmethod
    def get_accessible_groups(user):
        role = getattr(user, 'role', None)

        if role == 'admin':
            return Group.objects.select_related('id_generation').order_by(
                'academic_level', 'group_letter'
            )

        if role != 'teacher' or not getattr(user, 'is_authenticated', False):
            return Group.objects.none()

        try:
            profile = TeacherProfile.objects.get(user_id=user.pk)
        except TeacherProfile.DoesNotExist:
            return Group.objects.none()

        group_ids = (
            GroupTeacherAssignment.objects
            .filter(teacher=profile)
            .values_list('group_id', flat=True)
            .distinct()
        )

        return (
            Group.objects
            .select_related('id_generation')
            .filter(pk__in=group_ids, status=True)
            .order_by('academic_level', 'group_letter')
        )

    @staticmethod
    def _can_access_group(user, group_id: int) -> bool:
        if user is None or not getattr(user, 'is_authenticated', False):
            return False

        role = getattr(user, 'role', None)
        if role != 'teacher':
            return True

        return ReportService.get_accessible_groups(user).filter(pk=group_id).exists()

    @staticmethod
    def _build_group_students(qs):
        students_map = {}

        for assignment in qs:
            student_id = assignment.student_id
            student_info = students_map.setdefault(student_id, {
                'studentId': student_id,
                'matricula': getattr(assignment.student, 'matricula', ''),
                'fullName': (
                    f"{assignment.student.first_name} {assignment.student.last_name}".strip()
                    if assignment.student else ''
                ),
                'scores': [],
                'totalExams': 0,
            })

            student_info['totalExams'] += 1
            if assignment.score is not None:
                student_info['scores'].append(float(assignment.score))

        result = []
        for student_info in sorted(students_map.values(), key=lambda item: item['fullName'] or ''):
            scores = student_info['scores']
            average_grade = (sum(scores) / len(scores)) if scores else None
            approved = len([score for score in scores if score >= 70]) if scores else 0

            result.append({
                'studentId': student_info['studentId'],
                'matricula': student_info['matricula'],
                'fullName': student_info['fullName'],
                'totalExams': student_info['totalExams'],
                'averageGrade': round(average_grade, 2) if average_grade is not None else None,
                'approvalRate': (approved / len(scores)) * 100 if scores else None,
            })

        return result

    # ===== REPORT: BY EXAM =====

    @staticmethod
    def by_exam(data):
        exam = Exam.objects.select_related(
            'id_subject', 'id_teacher'
        ).filter(id_exam=data['examId']).first()

        # Keep the exam report aligned with the exam's currently assigned groups.
        current_group_ids = ExamGroupAssignment.objects.filter(
            exam_id=data['examId']
        ).values_list('group_id', flat=True)

        qs = ExamAssignment.objects.select_related(
            'exam',
            'exam__id_subject',
            'exam__id_teacher',
            'student'
        ).filter(
            exam_id=data['examId'],
            group_id__in=current_group_ids,
        )

        subject_name = ""
        teacher_name = ""

        if exam:
            subject_name = exam.id_subject.name if exam.id_subject else ""

            if exam.id_teacher:
                teacher_name = f"{exam.id_teacher.first_name} {exam.id_teacher.last_name}".strip()

        return {
            "examId": getattr(exam, "id_exam", None),
            "examTitle": getattr(exam, "title", ""),
            "subjectName": subject_name,
            "teacherName": teacher_name,
            "creationDate": getattr(exam, "creation_date", None),

            "metrics": ReportService._calculate_summary_metrics(qs),

            "statusBreakdown": {
                "pending": qs.filter(status="pending").count(),
                "inProgress": qs.filter(status="in_progress").count(),
                "finished": qs.filter(status="completed").count(),
                "notPresented": 0,
            },

            "gradeDistribution": ReportService._calculate_distribution(qs),

            "students": [
                {
                    "studentId": r.student_id,
                    "matricula": getattr(r.student, "matricula", ""),
                    "fullName": f"{r.student.first_name} {r.student.last_name}".strip() if r.student else "",
                    "grade": r.score,
                    "status": ReportService._map_status(r.status),
                    "startDatetime": r.available_from,
                    "endDatetime": r.attempt_date,
                }
                for r in qs
            ]
        }

    # ===== REPORT: BY GROUP =====

    @staticmethod
    def by_group(data, user=None):
        qs = ExamAssignment.objects.select_related(
            'student', 'group', 'exam'
        ).filter(group_id=data['groupId'])

        if user is not None and not ReportService._can_access_group(user, data['groupId']):
            raise PermissionDenied('No tienes acceso a este grupo.')

        # Traer el grupo directamente para no depender de que existan calificaciones.
        group = Group.objects.select_related('id_generation').filter(
            id_group=data['groupId']
        ).first()

        if group is None:
            return {
                'groupId': data['groupId'],
                'groupLetter': '',
                'academicLevel': 0,
                'generationYear': None,
                'metrics': ReportService._calculate_summary_metrics(qs),
                'gradeDistribution': ReportService._calculate_distribution(qs),
                'students': [],
            }

        result = ReportService._build_group_students(qs)

        return {
            'groupId': getattr(group, 'id_group', data['groupId']),
            'groupLetter': getattr(group, 'group_letter', ''),
            'academicLevel': getattr(group, 'academic_level', 0),
            'generationYear': getattr(group.id_generation, 'year', None) if group.id_generation else None,

            'metrics': ReportService._calculate_summary_metrics(qs),
            'gradeDistribution': ReportService._calculate_distribution(qs),

            'students': result
        }
    # ===== REPORT: BY STUDENT =====

    @staticmethod
    def by_student(data):
        qs = ExamAssignment.objects.select_related(
            'exam',
            'exam__id_subject',
            'student',
            'group'
        ).filter(student_id=data['studentId'])

        student = qs.first().student if qs.exists() else None
        group = qs.first().group if qs.exists() else None

        return {
            "studentId": data['studentId'],
            "matricula": getattr(student, "matricula", ""),
            "fullName": f"{student.first_name} {student.last_name}".strip() if student else "",

            "groupLetter": getattr(group, "group_letter", "") if group else "",
            "academicLevel": getattr(group, "academic_level", 0) if group else 0,

            "metrics": ReportService._calculate_summary_metrics(qs),
            "gradeDistribution": ReportService._calculate_distribution(qs),

            "exams": [
                {
                    "examId": r.exam_id,
                    "examTitle": r.exam.title,
                    "subjectName": r.exam.id_subject.name if r.exam.id_subject else "",
                    "grade": r.score,
                    "status": ReportService._map_status(r.status),
                    "startDatetime": r.available_from,
                    "endDatetime": r.attempt_date,
                }
                for r in qs
            ]
        }

    # ===== REPORT: STUDENT EXAM DETAIL =====

    @staticmethod
    def student_exam_detail(data):
        qs = ExamAssignment.objects.select_related(
            'exam',
            'exam__id_subject',
            'student'
        ).filter(
            student_id=data['studentId'],
            exam_id=data['examId']
        )

        assignment = qs.first()

        if not assignment:
            return {}

        return {
            "studentId": assignment.student_id,
            "matricula": getattr(assignment.student, "matricula", ""),
            "fullName": f"{assignment.student.first_name} {assignment.student.last_name}".strip(),

            "examId": assignment.exam_id,
            "examTitle": assignment.exam.title,
            "subjectName": assignment.exam.id_subject.name if assignment.exam.id_subject else "",

            "grade": assignment.score,
            "status": ReportService._map_status(assignment.status),

            "startDatetime": assignment.available_from,
            "endDatetime": assignment.attempt_date,

            "totalQuestions": 0,
            "correctAnswers": 0,
            "answers": []
        }