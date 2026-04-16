from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.academic.models import Generation, Group
from apps.users.models import User, StudentProfile
from apps.users.views import UserListCreateView


class UserListPermissionsTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()

		self.generation = Generation.objects.create(year=2031, total_levels=6, status=True)
		self.group = Group.objects.create(
			id_generation=self.generation,
			group_letter='A',
			academic_level=1,
			status=True,
		)

		self.admin_user = User.objects.create_user(
			username='admin-users',
			email='admin-users@example.com',
			role='admin',
			first_name='Admin',
			last_name='Users',
		)
		self.teacher_user = User.objects.create_user(
			username='teacher-users',
			email='teacher-users@example.com',
			role='teacher',
			first_name='Teacher',
			last_name='Users',
		)
		self.student_user = User.objects.create_user(
			username='student-users',
			email='student-users@example.com',
			role='student',
			first_name='Student',
			last_name='Users',
			matricula='2031001',
		)
		StudentProfile.objects.create(user=self.student_user, group=self.group)

	def test_teacher_can_list_students_by_group_with_group_param(self):
		request = self.factory.get(
			f'/api/users/?page=1&page_size=100&role=student&group={self.group.pk}'
		)
		force_authenticate(request, user=self.teacher_user)

		response = UserListCreateView.as_view()(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['count'], 1)
		self.assertEqual(response.data['results'][0]['role'], 'student')

	def test_teacher_cannot_list_users_without_group_scope(self):
		request = self.factory.get('/api/users/?page=1&page_size=100&role=student')
		force_authenticate(request, user=self.teacher_user)

		response = UserListCreateView.as_view()(request)

		self.assertEqual(response.status_code, 403)

	def test_admin_still_can_list_users(self):
		request = self.factory.get('/api/users/?page=1&page_size=100')
		force_authenticate(request, user=self.admin_user)

		response = UserListCreateView.as_view()(request)

		self.assertEqual(response.status_code, 200)
