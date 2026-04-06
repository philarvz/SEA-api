from django.contrib import admin

from .models import Question, Answer, CodeQuestion


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id_question', 'statement', 'question_type', 'difficulty', 'id_subject', 'status')
    list_filter = ('question_type', 'difficulty', 'status')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id_answer', 'id_question', 'answer_text', 'is_correct')


@admin.register(CodeQuestion)
class CodeQuestionAdmin(admin.ModelAdmin):
    list_display = ('question', 'language')
