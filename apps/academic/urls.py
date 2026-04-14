"""
URL configuration for the Academic module.
Base path: /api/academic/
"""

from django.urls import path
from .views import (
    GenerationListCreateView,
    GenerationDetailView,
    GenerationStatusView,
    PeriodListCreateView,
    PeriodCurrentView,
    PeriodDetailView,
    PeriodStatusView,
    PeriodAdvanceGroupsView,
    GroupListCreateView,
    GroupDetailView,
    GroupStatusView,
    GroupAssignStudentView,
    GroupAssignmentsView,
    GroupAssignmentDetailView,
    GroupAvailableTeachersView,
    GroupStudentsView,
    TeacherMyGroupsView,
    SubjectListCreateView,
    SubjectDetailView,
    SubjectUnitsBySubjectView,
    SubjectStatusView,
    TeacherSubjectsView,
)

app_name = 'academic'

urlpatterns = [
    # ------------------------------------------------------------------
    # Generation endpoints  (GEN-001, GEN-002)
    # ------------------------------------------------------------------
    path('generations/', GenerationListCreateView.as_view(), name='generation-list-create'),
    path('generations/<int:pk>/', GenerationDetailView.as_view(), name='generation-detail'),
    path('generations/<int:pk>/status/', GenerationStatusView.as_view(), name='generation-status'),

    # ------------------------------------------------------------------
    # Period endpoints  (PER-001, PER-002, PER-003)
    # ------------------------------------------------------------------
    path('periods/', PeriodListCreateView.as_view(), name='period-list-create'),
    path('periods/current/', PeriodCurrentView.as_view(), name='period-current'),
    path('periods/<int:pk>/', PeriodDetailView.as_view(), name='period-detail'),
    path('periods/<int:pk>/status/', PeriodStatusView.as_view(), name='period-status'),
    path('periods/<int:pk>/advance-groups/', PeriodAdvanceGroupsView.as_view(), name='period-advance-groups'),

    # ------------------------------------------------------------------
    # Group endpoints  (GG-001 → GG-004)
    # ------------------------------------------------------------------
    path('groups/', GroupListCreateView.as_view(), name='group-list-create'),
    path('groups/my-groups/', TeacherMyGroupsView.as_view(), name='teacher-my-groups'),
    path('groups/<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('groups/<int:pk>/status/', GroupStatusView.as_view(), name='group-status'),
    path('groups/<int:pk>/assign-student/', GroupAssignStudentView.as_view(), name='group-assign-student'),
    path('groups/<int:pk>/assignments/', GroupAssignmentsView.as_view(), name='group-assignments'),
    path('groups/<int:pk>/assignments/<int:a_pk>/', GroupAssignmentDetailView.as_view(), name='group-assignment-detail'),
    path('groups/<int:pk>/available-teachers/', GroupAvailableTeachersView.as_view(), name='group-available-teachers'),
    path('groups/<int:pk>/students/', GroupStudentsView.as_view(), name='group-students'),

    # ------------------------------------------------------------------
    # Subject endpoints  (MAT-001 → MAT-003, TC-001)
    # ------------------------------------------------------------------
    path('subjects/my-subjects/', TeacherSubjectsView.as_view(), name='teacher-subjects'),
    path('subjects/', SubjectListCreateView.as_view(), name='subject-list-create'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject-detail'),
    path('subjects/<int:pk>/units/', SubjectUnitsBySubjectView.as_view(), name='subject-units-by-subject'),
    path('subjects/<int:pk>/status/', SubjectStatusView.as_view(), name='subject-status'),
]
