from django.contrib import admin

from .models import StudentAnswer


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'id_student_answer', 'exam_assignment', 'question',
        'is_correct', 'score', 'evaluated_at',
    )
    list_filter = ('is_correct', 'evaluated_at')
    search_fields = ('exam_assignment__id_assignment', 'question__id_question')
