"""
Serializers for the Question bank (CRUD, nested answers, code questions).
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Question, Answer, CodeQuestion


QUESTION_TYPE_VALUES = {c[0] for c in Question.QUESTION_TYPE_CHOICES}


def _normalize_type(value: str) -> str:
    if not value:
        return 'MULTIPLE_CHOICE'
    s = str(value).strip().upper().replace('-', '_').replace(' ', '_')
    aliases = {
        'MC': 'MULTIPLE_CHOICE',
        'MS': 'MULTIPLE_SELECTION',
    }
    if s in aliases:
        return aliases[s]
    if s in QUESTION_TYPE_VALUES:
        return s
    from .excel_upload import parse_question_type

    return parse_question_type(value)


class AnswerOptionSerializer(serializers.ModelSerializer):
    """Maps Answer model to option payloads (max 4 per question, validated in QuestionSerializer)."""

    id = serializers.IntegerField(source='id_answer', read_only=True)
    text = serializers.CharField(source='answer_text')

    class Meta:
        model = Answer
        fields = ('id', 'text', 'is_correct')
        read_only_fields = ('id',)

    def validate_text(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El texto de la opción no puede estar vacío.')
        return value


class CodeQuestionPayloadSerializer(serializers.Serializer):
    language = serializers.CharField(max_length=32, default='python', required=False)
    test_cases = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )

    def validate_test_cases(self, value):
        return value if value is not None else []


@extend_schema_field({
    'type': 'object',
    'nullable': True,
    'properties': {
        'language': {'type': 'string', 'example': 'python'},
        'test_cases': {'type': 'array', 'items': {'type': 'string'}},
    },
})
class CodeQuestionField(serializers.Field):
    """Read/write helper: avoids OneToOne DoesNotExist issues on serialization."""

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('allow_null', True)
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        cq = CodeQuestion.objects.filter(question=instance).first()
        if not cq:
            return None
        return {
            'language': cq.language,
            'test_cases': cq.test_cases,
        }

    def to_internal_value(self, data):
        if data in (None, '', {}):
            return None
        ser = CodeQuestionPayloadSerializer(data=data)
        ser.is_valid(raise_exception=True)
        return ser.validated_data


class QuestionSerializer(serializers.ModelSerializer):
    """Create / read / update with nested answer_options and optional code_question."""

    id = serializers.IntegerField(source='id_question', read_only=True)
    text = serializers.CharField(source='statement')
    answer_options = AnswerOptionSerializer(many=True, source='answers', required=False)
    code_question = CodeQuestionField()

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'question_type',
            'difficulty',
            'bloom_level',
            'image_url',
            'points',
            'id_subject',
            'status',
            'answer_options',
            'code_question',
            'created_at',
            'modified_at',
            'modified_by',
        )
        read_only_fields = ('created_at', 'modified_at', 'modified_by', 'id')

    def validate_text(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El enunciado es obligatorio.')
        return value

    def validate(self, attrs):
        instance = self.instance
        qtype = attrs.get('question_type')
        if qtype is None and instance is not None:
            qtype = instance.question_type

        if self.partial and instance is not None:
            if 'answer_options' not in self.initial_data and 'answers' not in self.initial_data:
                options = list(instance.answers.all())
            else:
                options = attrs.get('answers')
        else:
            options = attrs.get('answers')

        if options is None:
            options = []

        code_in = attrs.get('code_question')
        if self.partial and instance is not None and 'code_question' not in self.initial_data:
            cq = CodeQuestion.objects.filter(question=instance).first()
            code_in = {'language': cq.language, 'test_cases': cq.test_cases} if cq else None
        elif 'code_question' in self.initial_data:
            raw_cq = self.initial_data.get('code_question')
            if raw_cq in (None, {}):
                code_in = None
            elif isinstance(raw_cq, dict):
                ser = CodeQuestionPayloadSerializer(data=raw_cq)
                ser.is_valid(raise_exception=True)
                code_in = ser.validated_data

        self._validate_type_rules(qtype, options, code_in)
        return attrs

    def _validate_type_rules(self, qtype, options, code_in):
        if not qtype:
            return

        if isinstance(options, list):
            n = len(options)
        else:
            n = options.count()

        if qtype == 'OPEN':
            if n > 0:
                raise serializers.ValidationError({
                    'answer_options': 'Las preguntas abiertas no deben tener opciones.',
                })
            return

        if qtype == 'CODE':
            if n > 0:
                raise serializers.ValidationError({
                    'answer_options': 'Las preguntas de código no deben tener opciones.',
                })
            tests = (code_in or {}).get('test_cases') if isinstance(code_in, dict) else None
            if not tests:
                raise serializers.ValidationError({
                    'code_question': 'Las preguntas de tipo código requieren test_cases.',
                })
            return

        if n < 2:
            raise serializers.ValidationError({
                'answer_options': 'Se requieren entre 2 y 4 opciones para preguntas de opción múltiple.',
            })
        if n > 4:
            raise serializers.ValidationError({
                'answer_options': 'Máximo 4 opciones permitidas.',
            })

        if isinstance(options, list) and options and isinstance(options[0], Answer):
            correct_count = sum(1 for o in options if o.is_correct)
        elif isinstance(options, list):
            correct_count = sum(1 for o in options if o.get('is_correct'))
        else:
            correct_count = sum(1 for o in options if o.is_correct)

        if qtype == 'MULTIPLE_CHOICE' and correct_count != 1:
            raise serializers.ValidationError({
                'answer_options': 'Debe haber exactamente una respuesta correcta.',
            })
        if qtype == 'MULTIPLE_SELECTION' and correct_count < 1:
            raise serializers.ValidationError({
                'answer_options': 'Debe marcar al menos una respuesta correcta.',
            })

    def create(self, validated_data):
        answers_data = validated_data.pop('answers', [])
        code_data = validated_data.pop('code_question', None)

        question = Question.objects.create(**validated_data)

        for opt in answers_data:
            text = opt.get('answer_text')
            if text is None:
                text = opt.get('text', '')
            Answer.objects.create(
                id_question=question,
                answer_text=text,
                is_correct=bool(opt.get('is_correct')),
            )

        if question.question_type == 'CODE' and code_data:
            CodeQuestion.objects.create(
                question=question,
                language=code_data.get('language', 'python'),
                test_cases=code_data.get('test_cases') or [],
            )

        return question

    def update(self, instance, validated_data):
        answers_data = validated_data.pop('answers', None)
        code_data = validated_data.pop('code_question', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if answers_data is not None:
            instance.answers.all().delete()
            for opt in answers_data:
                text = opt.get('answer_text')
                if text is None:
                    text = opt.get('text', '')
                Answer.objects.create(
                    id_question=instance,
                    answer_text=text,
                    is_correct=bool(opt.get('is_correct')),
                )

        if instance.question_type == 'CODE':
            if code_data is not None:
                CodeQuestion.objects.update_or_create(
                    question=instance,
                    defaults={
                        'language': code_data.get('language', 'python'),
                        'test_cases': code_data.get('test_cases') or [],
                    },
                )
        else:
            CodeQuestion.objects.filter(question=instance).delete()

        return instance


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight row for tables."""

    id = serializers.IntegerField(source='id_question', read_only=True)
    text = serializers.CharField(source='statement', read_only=True)

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'question_type',
            'difficulty',
            'bloom_level',
            'points',
            'id_subject',
            'status',
            'created_at',
            'modified_at',
        )
        read_only_fields = fields
