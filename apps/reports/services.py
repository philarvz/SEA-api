from django.db.models import Avg, Max, Min
from apps.exams.models import ExamAssignment


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
        qs = ExamAssignment.objects.select_related(
            'exam',
            'exam__id_subject',
            'exam__id_teacher',
            'student'
        ).filter(exam_id=data['examId'])

        exam = qs.first().exam if qs.exists() else None

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
    def by_group(data):
        qs = ExamAssignment.objects.select_related(
            'student', 'group', 'exam'
        ).filter(group_id=data['groupId'])

        students_map = {}

        for r in qs:
            sid = r.student_id

            students_map.setdefault(sid, {
                "studentId": sid,
                "matricula": getattr(r.student, "matricula", ""),
                "fullName": f"{r.student.first_name} {r.student.last_name}".strip() if r.student else "",
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

        group = qs.first().group if qs.exists() else None

        return {
            "groupId": getattr(group, "id_group", data['groupId']),
            "groupLetter": getattr(group, "group_letter", "") if group else "",
            "academicLevel": getattr(group, "academic_level", 0) if group else 0,
            "generationYear": getattr(group.id_generation, "year", None) if group and hasattr(group, "id_generation") else None,

            "metrics": ReportService._calculate_summary_metrics(qs),
            "gradeDistribution": ReportService._calculate_distribution(qs),

            "students": result
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