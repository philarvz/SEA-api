"""
Exams URL Configuration
"""

from django.urls import path
from .views import QuestionTemplateDownloadView

app_name = 'exams'

urlpatterns = [
    path('template/download/', QuestionTemplateDownloadView.as_view(), name='question-template-download'),
]