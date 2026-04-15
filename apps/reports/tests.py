from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.academic.models import Generation, Group, GroupTeacherAssignment, Subject
from apps.exams.models import Exam, ExamAssignment, ExamGroupAssignment
from apps.reports.services import ReportService
from apps.reports.views import AccessibleGroupsView
from apps.users.models import TeacherProfile, User


class ReportServiceTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()

		self.generation = Generation.objects.create(year=2024, total_levels=6, status=True)
		self.group_a = Group.objects.create(
			id_generation=self.generation,
			group_letter='A',
			academic_level=1,
			status=True,
		)
		self.group_b = Group.objects.create(
			id_generation=self.generation,
			group_letter='B',
			academic_level=1,
			status=True,
		)
		self.subject = Subject.objects.create(name='Matemáticas', level_number=1, status=True)

		self.admin_user = User.objects.create_user(
			username='admin',
			email='admin@example.com',
			role='admin',
			first_name='Admin',
			last_name='User',
		)
		self.teacher_user = User.objects.create_user(
			username='teacher',
			email='teacher@example.com',
			role='teacher',
			first_name='Teach',
			last_name='Er',
		)
		self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user)
		self.teacher_profile.subjects.add(self.subject)
		GroupTeacherAssignment.objects.create(
			group=self.group_a,
			teacher=self.teacher_profile,
			subject=self.subject,
		)

		self.student = User.objects.create_user(
			username='student',
			email='student@example.com',
			role='student',
			first_name='Stu',
			last_name='Dent',
			matricula='2024001',
		)

		self.exam = Exam.objects.create(
			id_subject=self.subject,
			id_teacher=self.teacher_user,
			title='Examen 1',
			name='Examen 1',
			unit_number=1,
			difficulty_level='medium',
			secure_mode=True,
			minimum_score=8,
			creation_date=timezone.now(),
			status=True,
		)

		now = timezone.now()
		ExamAssignment.objects.create(
			exam=self.exam,
			student=self.student,
			group=self.group_a,
			status='pending',
			score=None,
			is_passed=None,
			assigned_at=now,
			available_from=now,
			available_to=now + timedelta(days=7),
		)

		ExamGroupAssignment.objects.create(
			exam=self.exam,
			group=self.group_a,
			available_from=now,
			available_to=now + timedelta(days=7),
		)

	def test_by_group_includes_students_without_score(self):
		data = ReportService.by_group({'groupId': self.group_a.pk}, user=self.teacher_user)

		self.assertEqual(data['groupId'], self.group_a.pk)
		self.assertEqual(len(data['students']), 1)
		self.assertEqual(data['students'][0]['studentId'], self.student.pk)
		self.assertEqual(data['students'][0]['totalExams'], 1)
		self.assertIsNone(data['students'][0]['averageGrade'])

	def test_teacher_only_sees_assigned_groups(self):
		groups = ReportService.get_accessible_groups(self.teacher_user)

		self.assertEqual(list(groups.values_list('pk', flat=True)), [self.group_a.pk])

	def test_admin_sees_all_groups(self):
		groups = ReportService.get_accessible_groups(self.admin_user)

		self.assertCountEqual(list(groups.values_list('pk', flat=True)), [self.group_a.pk, self.group_b.pk])

	def test_report_groups_view_returns_serializer_payload(self):
		request = self.factory.get('/api/reports/groups/')
		force_authenticate(request, user=self.teacher_user)

		response = AccessibleGroupsView.as_view()(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data['data']), 1)
		self.assertEqual(response.data['data'][0]['id_group'], self.group_a.pk)

	def test_by_exam_excludes_assignments_from_groups_not_currently_assigned(self):
		other_generation = Generation.objects.create(year=2035, total_levels=6, status=True)
		other_group = Group.objects.create(
			id_generation=other_generation,
			group_letter='A',
			academic_level=1,
			status=True,
		)
		other_student = User.objects.create_user(
			username='student-other',
			email='student-other@example.com',
			role='student',
			first_name='Other',
			last_name='Student',
			matricula='2024999',
		)

		now = timezone.now()
		ExamAssignment.objects.create(
			exam=self.exam,
			student=other_student,
			group=other_group,
			status='completed',
			score=90,
			is_passed=True,
			assigned_at=now,
			available_from=now,
			available_to=now + timedelta(days=7),
			attempt_date=now,
		)

		data = ReportService.by_exam({'examId': self.exam.pk})

		# The stale assignment in another group should not affect this exam report.
		self.assertEqual(data['metrics']['totalStudents'], 1)
		self.assertEqual(data['statusBreakdown']['finished'], 0)

	def test_summary_metrics_count_distinct_students(self):
		other_student = User.objects.create_user(
			username='student-metrics',
			email='student-metrics@example.com',
			role='student',
			first_name='Metric',
			last_name='Student',
			matricula='2024555',
		)
		now = timezone.now()
		ExamAssignment.objects.create(
			exam=self.exam,
			student=other_student,
			group=self.group_a,
			status='completed',
			score=80,
			is_passed=True,
			assigned_at=now,
			available_from=now,
			available_to=now + timedelta(days=7),
			attempt_date=now,
		)

		data = ReportService.by_group({'groupId': self.group_a.pk}, user=self.teacher_user)

		self.assertEqual(data['metrics']['totalExams'], 2)
		self.assertEqual(data['metrics']['totalStudents'], 2)
