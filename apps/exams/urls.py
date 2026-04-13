"""
Exams URL Configuration
Base path: /api/exams/
"""

from django.urls import path
from .views import (
    ExamListCreateView,
    ExamDetailView,
    ExamQuestionsView,
    ExamStatusView,
    ExamSecureModeView,
    ExamDeleteView,
    QuestionTemplateDownloadView,
    ExamAssignView,
    ExamGroupStatsView,
    ExamGroupStatsByGroupView,
    ExamGroupStudentsView,
    ExamGradeExportExcelView,
    ExamGradeExportPDFView,
    MyAssignmentsView,
    CreatedByMeExamsView,
)

app_name = 'exams'

urlpatterns = [
    # ------------------------------------------------------------------
    # Exam CRUD endpoints
    # ------------------------------------------------------------------
    path('', ExamListCreateView.as_view(), name='exam-list-create'),
    path('<int:pk>/', ExamDetailView.as_view(), name='exam-detail'),
    path('<int:exam_id>/questions/', ExamQuestionsView.as_view(), name='exam-questions'),
    path('<int:pk>/status/', ExamStatusView.as_view(), name='exam-status'),
    path('<int:pk>/secure-mode/', ExamSecureModeView.as_view(), name='exam-secure-mode'),
    path('<int:pk>/delete/', ExamDeleteView.as_view(), name='exam-delete'),
    path('<int:exam_id>/stats/groups/', ExamGroupStatsView.as_view(), name='exam-group-stats'),
    path('<int:exam_id>/stats/groups/<int:group_id>/', ExamGroupStatsByGroupView.as_view(), name='exam-group-stats-single'),
    path('<int:exam_id>/groups/<int:group_id>/students/', ExamGroupStudentsView.as_view(), name='exam-group-students'),
    path('<int:exam_id>/grades/groups/<int:group_id>/export/excel/', ExamGradeExportExcelView.as_view(), name='exam-grade-export-excel'),
    path('<int:exam_id>/grades/groups/<int:group_id>/export/pdf/', ExamGradeExportPDFView.as_view(), name='exam-grade-export-pdf'),
    path('created-by-me/', CreatedByMeExamsView.as_view(), name='exam-created-by-me'),

    # ------------------------------------------------------------------
    # Exam assignments
    # ------------------------------------------------------------------
    path('exam-assignments/assign/', ExamAssignView.as_view(), name='exam-assign'),
    path('exam-assignments/my-assignments/', MyAssignmentsView.as_view(), name='my-assignments'),

    # ------------------------------------------------------------------
    # Template download (existing)
    # ------------------------------------------------------------------
    path('template/download/', QuestionTemplateDownloadView.as_view(), name='question-template-download'),
]