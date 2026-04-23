from django.db.models import Avg, Max, Min
from apps.exams.models import ExamAssignment
from apps.academic.models import Group  # IMPORTANTE
from apps.reports.models import VwExamAssignmentDetail, VwExamGroupStats


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
        total = qs.count()

        avg = qs.aggregate(avg=Avg('score'))['avg'] or 0
        highest = qs.aggregate(max=Max('score'))['max']
        lowest = qs.aggregate(min=Min('score'))['min']
        approved = qs.filter(score__gte=70).count()

        return {
            "totalStudents": total,
            "totalExams": total,
            "averageGrade": avg,
            "approvalRate": (approved / total * 100) if total else 0,
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

    # ===== REPORT: BY EXAM =====

    @staticmethod
    def by_exam(data):
        # Consulta principal usando la vista vw_exam_assignment_detail
        vw_qs = VwExamAssignmentDetail.objects.filter(exam_id=data['examId'])
        first = vw_qs.first()

        subject_name = first.subject_name if first else ""
        teacher_name = f"{first.teacher_first_name} {first.teacher_last_name}".strip() if first else ""

        # Métricas se calculan sobre la tabla original (permite agregaciones Django)
        qs = ExamAssignment.objects.filter(exam_id=data['examId'])

        return {
            "examId": first.exam_id if first else None,
            "examTitle": first.exam_title if first else "",
            "subjectName": subject_name,
            "teacherName": teacher_name,
            "creationDate": first.exam_creation_date if first else None,

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
                    "matricula": r.student_matricula or "",
                    "fullName": f"{r.student_first_name} {r.student_last_name}".strip(),
                    "grade": r.score,
                    "status": ReportService._map_status(r.assignment_status),
                    "startDatetime": r.available_from,
                    "endDatetime": r.attempt_date,
                }
                for r in vw_qs
            ]
        }

    # ===== REPORT: BY GROUP =====

    @staticmethod
    def by_group(data):
        # Consulta principal usando la vista vw_exam_assignment_detail
        vw_qs = VwExamAssignmentDetail.objects.filter(group_id=data['groupId'])

        # Datos del grupo
        group = Group.objects.select_related('id_generation').filter(
            id_group=data['groupId']
        ).first()

        students_map = {}

        for r in vw_qs:
            sid = r.student_id

            students_map.setdefault(sid, {
                "studentId": sid,
                "matricula": r.student_matricula or "",
                "fullName": f"{r.student_first_name} {r.student_last_name}".strip(),
                "scores": [],
            })

            if r.score is not None:
                students_map[sid]["scores"].append(float(r.score))

        result = []

        for s in students_map.values():
            scores = s["scores"]
            if not scores:
                continue

            avg = sum(scores) / len(scores)
            approved = len([x for x in scores if x >= 70])

            result.append({
                "studentId": s["studentId"],
                "matricula": s["matricula"],
                "fullName": s["fullName"],
                "totalExams": len(scores),
                "averageGrade": avg,
                "approvalRate": (approved / len(scores)) * 100,
            })

        # Métricas sobre la tabla original
        qs = ExamAssignment.objects.filter(group_id=data['groupId'])

        return {
            "groupId": getattr(group, "id_group", data['groupId']),
            "groupLetter": getattr(group, "group_letter", "") if group else "",
            "academicLevel": getattr(group, "academic_level", 0) if group else 0,
            "generationYear": getattr(group.id_generation, "year", None) if group and group.id_generation else None,

            "metrics": ReportService._calculate_summary_metrics(qs),
            "gradeDistribution": ReportService._calculate_distribution(qs),

            "students": result
        }
    # ===== REPORT: BY STUDENT =====

    @staticmethod
    def by_student(data):
        # Consulta principal usando la vista vw_exam_assignment_detail
        vw_qs = VwExamAssignmentDetail.objects.filter(student_id=data['studentId'])
        first = vw_qs.first()

        # Métricas se calculan sobre la tabla original
        qs = ExamAssignment.objects.filter(student_id=data['studentId'])

        return {
            "studentId": data['studentId'],
            "matricula": first.student_matricula or "" if first else "",
            "fullName": f"{first.student_first_name} {first.student_last_name}".strip() if first else "",

            "groupLetter": first.group_letter if first else "",
            "academicLevel": first.academic_level if first else 0,

            "metrics": ReportService._calculate_summary_metrics(qs),
            "gradeDistribution": ReportService._calculate_distribution(qs),

            "exams": [
                {
                    "examId": r.exam_id,
                    "examTitle": r.exam_title,
                    "subjectName": r.subject_name,
                    "grade": r.score,
                    "status": ReportService._map_status(r.assignment_status),
                    "startDatetime": r.available_from,
                    "endDatetime": r.attempt_date,
                }
                for r in vw_qs
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

    # ===== REPORT: GROUP STATS (via database view) =====

    @staticmethod
    def group_stats_from_view(exam_id):
        """
        Devuelve estadísticas por grupo para un examen usando
        la vista materializada vw_exam_group_stats.
        Elimina JOINs y agregaciones en tiempo de ejecución.
        """
        rows = VwExamGroupStats.objects.filter(exam_id=exam_id)

        return [
            {
                "examId": r.exam_id,
                "examName": r.exam_name,
                "groupId": r.group_id,
                "groupLabel": f"{r.academic_level}{r.group_letter} (Gen {r.generation_year})",
                "totalStudents": r.total_students,
                "averageScore": r.average_score,
                "highestScore": r.highest_score,
                "lowestScore": r.lowest_score,
                "approvalRate": r.approval_rate,
                "pendingCount": r.pending_count,
                "inProgressCount": r.in_progress_count,
                "completedCount": r.completed_count,
            }
            for r in rows
        ]