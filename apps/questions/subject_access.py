from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser

from apps.users.models import TeacherProfile


def allowed_subject_ids_for_question_user(user: AbstractBaseUser | None) -> frozenset[int] | None:
    if user is None or not getattr(user, 'is_authenticated', False):
        return frozenset()
    role = getattr(user, 'role', None)
    if role == 'admin':
        return None
    if role != 'teacher':
        return frozenset()
    try:
        profile = TeacherProfile.objects.get(user_id=user.pk)
    except TeacherProfile.DoesNotExist:
        return frozenset()
    return frozenset(profile.subjects.values_list('id_subject', flat=True))
