from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.academic.models import Generation, Group
from apps.academic.views import GroupStudentsView
from apps.users.models import StudentProfile, User


class GroupStudentsViewTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()

		self.generation = Generation.objects.create(year=2030, total_levels=6, status=True)
		self.group = Group.objects.create(
			id_generation=self.generation,
			group_letter='A',
			academic_level=1,
			status=True,
		)

		self.admin_user = User.objects.create_user(
			username='admin-academic',
			email='admin-academic@example.com',
			role='admin',
			first_name='Admin',
			last_name='Academic',
		)
		self.teacher_user = User.objects.create_user(
			username='teacher-academic',
			email='teacher-academic@example.com',
			role='teacher',
			first_name='Teacher',
			last_name='Academic',
		)
		self.student_user = User.objects.create_user(
			username='student-academic',
			email='student-academic@example.com',
			role='student',
			first_name='Student',
			last_name='Academic',
			matricula='2030001',
		)
		StudentProfile.objects.create(user=self.student_user, group=self.group)

	def test_admin_can_list_group_students(self):
		request = self.factory.get(f'/api/academic/groups/{self.group.pk}/students/')
		force_authenticate(request, user=self.admin_user)

		response = GroupStudentsView.as_view()(request, pk=self.group.pk)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['success'], True)
		self.assertEqual(len(response.data['data']['results']), 1)

	def test_teacher_can_list_group_students(self):
		request = self.factory.get(f'/api/academic/groups/{self.group.pk}/students/')
		force_authenticate(request, user=self.teacher_user)

		response = GroupStudentsView.as_view()(request, pk=self.group.pk)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['success'], True)
		self.assertEqual(len(response.data['data']['results']), 1)
