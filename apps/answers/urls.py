from django.urls import path

from .views import AssignmentAnswersView, ForfeitExamView, ManualGradeAnswerView, SubmitExamAnswersView

app_name = 'answers'

urlpatterns = [
    path('submit/', SubmitExamAnswersView.as_view(), name='submit-answers'),
    path('forfeit/', ForfeitExamView.as_view(), name='forfeit-exam'),
    path('manual-grade/', ManualGradeAnswerView.as_view(), name='manual-grade-answer'),
    path('assignment/<int:assignment_id>/', AssignmentAnswersView.as_view(), name='assignment-answers'),
]
