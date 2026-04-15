from django.urls import path
from .views import (
    ByExamView,
    ByGroupView,
    AccessibleGroupsView,
    ByStudentView,
    StudentExamDetailView,
)

urlpatterns = [
    path('groups/', AccessibleGroupsView.as_view()),
    path('by-exam/', ByExamView.as_view()),
    path('by-group/', ByGroupView.as_view()),
    path('by-student/', ByStudentView.as_view()),
    path('student-exam-detail/', StudentExamDetailView.as_view()),
]