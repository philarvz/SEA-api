"""
Exams URL Configuration
Base path: /api/exams/
"""

from django.urls import path
from .views import (
    ExamListCreateView,
    ExamDetailView,
    ExamStatusView,
    ExamSecureModeView,
    ExamDeleteView,
    QuestionTemplateDownloadView,
    ExamAssignView,
)

app_name = 'exams'

urlpatterns = [
    # ------------------------------------------------------------------
    # Exam CRUD endpoints
    # ------------------------------------------------------------------
    path('', ExamListCreateView.as_view(), name='exam-list-create'),
    path('<int:pk>/', ExamDetailView.as_view(), name='exam-detail'),
    path('<int:pk>/status/', ExamStatusView.as_view(), name='exam-status'),
    path('<int:pk>/secure-mode/', ExamSecureModeView.as_view(), name='exam-secure-mode'),
    path('<int:pk>/delete/', ExamDeleteView.as_view(), name='exam-delete'),

    # ------------------------------------------------------------------
    # Exam assignments
    # ------------------------------------------------------------------
    path('exam-assignments/assign/', ExamAssignView.as_view(), name='exam-assign'),

    # ------------------------------------------------------------------
    # Template download (existing)
    # ------------------------------------------------------------------
    path('template/download/', QuestionTemplateDownloadView.as_view(), name='question-template-download'),
]