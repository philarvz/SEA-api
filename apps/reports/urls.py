from django.urls import path
from .views import (
    ByExamView,
    ByGroupView,
    ByStudentView,
    StudentExamDetailView,
    ExamGroupStatsView,
)

urlpatterns = [
    path('by-exam/', ByExamView.as_view()),
    path('by-group/', ByGroupView.as_view()),
    path('by-student/', ByStudentView.as_view()),
    path('student-exam-detail/', StudentExamDetailView.as_view()),
    path('exam-group-stats/', ExamGroupStatsView.as_view()),
]