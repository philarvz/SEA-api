from decimal import Decimal

from rest_framework import serializers

from utils.sanitizers import MAX_CODE_LENGTH, MAX_STATEMENT_LENGTH
from .models import StudentAnswer


class StudentAnswerSerializer(serializers.ModelSerializer):
    selected_answers = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    question_statement = serializers.CharField(source='question.statement', read_only=True)
    question_image_url = serializers.CharField(source='question.image_url', read_only=True, allow_null=True)
    question_points = serializers.IntegerField(source='question.points', read_only=True)
    question_difficulty = serializers.CharField(source='question.difficulty', read_only=True)
    question_bloom_level = serializers.CharField(source='question.bloom_level', read_only=True)

    # Text of the option the student selected (MULTIPLE_CHOICE)
    selected_answer_text = serializers.CharField(
        source='selected_answer.answer_text',
        read_only=True,
        allow_null=True,
        default=None,
    )

    # Texts of all options the student selected (MULTIPLE_SELECTION)
    selected_answers_texts = serializers.SerializerMethodField()

    # Correct answer text(s) for display when student answered wrong
    correct_answer_text = serializers.SerializerMethodField()
    correct_answers_texts = serializers.SerializerMethodField()

    class Meta:
        model = StudentAnswer
        fields = [
            'id_student_answer',
            'exam_assignment',
            'question',
            'question_type',
            'question_statement',
            'question_image_url',
            'question_points',
            'question_difficulty',
            'question_bloom_level',
            'selected_answer',
            'selected_answer_text',
            'selected_answers',
            'selected_answers_texts',
            'correct_answer_text',
            'correct_answers_texts',
            'answer_text',
            'code_answer',
            'is_correct',
            'score',
            'evaluated_at',
            'created_at',
            'modified_at',
        ]
        read_only_fields = fields

    def get_selected_answers_texts(self, obj):
        return [a.answer_text for a in obj.selected_answers.all()]

    def get_correct_answer_text(self, obj):
        """Single correct answer text for MULTIPLE_CHOICE questions."""
        if obj.question.question_type != 'MULTIPLE_CHOICE':
            return None
        correct = obj.question.answers.filter(is_correct=True).first()
        return correct.answer_text if correct else None

    def get_correct_answers_texts(self, obj):
        """All correct answer texts for MULTIPLE_SELECTION questions."""
        if obj.question.question_type != 'MULTIPLE_SELECTION':
            return []
        return list(obj.question.answers.filter(is_correct=True).values_list('answer_text', flat=True))


class AnswerItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    selected_answer = serializers.IntegerField(required=False, allow_null=True)
    selected_answers = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
    )
    answer_text = serializers.CharField(required=False, allow_blank=False, max_length=MAX_STATEMENT_LENGTH)
    code_answer = serializers.CharField(required=False, allow_blank=False, max_length=MAX_CODE_LENGTH)

    def validate(self, attrs):
        provided = [
            'selected_answer' in attrs and attrs.get('selected_answer') is not None,
            'selected_answers' in attrs and len(attrs.get('selected_answers', [])) > 0,
            'answer_text' in attrs and attrs.get('answer_text', '').strip() != '',
            'code_answer' in attrs and attrs.get('code_answer', '').strip() != '',
        ]
        if sum(provided) != 1:
            raise serializers.ValidationError(
                'Debe enviar exactamente un tipo de respuesta por pregunta.'
            )
        return attrs


class SubmitExamSerializer(serializers.Serializer):
    exam_assignment_id = serializers.IntegerField(min_value=1)
    answers = AnswerItemSerializer(many=True, allow_empty=False)

    def validate_answers(self, value):
        question_ids = [item['question_id'] for item in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError('No se permiten preguntas duplicadas en el envio.')
        return value


class ManualGradeSerializer(serializers.Serializer):
    student_answer_id = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0'))
    is_correct = serializers.BooleanField()


class ForfeitExamSerializer(serializers.Serializer):
    """Used when a student abandons/exits a secure-mode exam; allows empty answers."""
    exam_assignment_id = serializers.IntegerField(min_value=1)
    answers = AnswerItemSerializer(many=True, allow_empty=True, required=False, default=list)

    def validate_answers(self, value):
        question_ids = [item['question_id'] for item in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError('No se permiten preguntas duplicadas en el envío.')
        return value
