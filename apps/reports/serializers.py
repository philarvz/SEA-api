from rest_framework import serializers


# ===== BASE =====
class BaseReportSerializer(serializers.Serializer):
    dateFrom = serializers.DateField(required=False)
    dateTo = serializers.DateField(required=False)


# ===== ENDPOINTS =====

class ByExamSerializer(BaseReportSerializer):
    examId = serializers.IntegerField(required=True)


class ByGroupSerializer(BaseReportSerializer):
    groupId = serializers.IntegerField(required=True)


class ByStudentSerializer(BaseReportSerializer):
    studentId = serializers.IntegerField(required=True)


class StudentExamDetailSerializer(serializers.Serializer):
    studentId = serializers.IntegerField(required=True)
    examId = serializers.IntegerField(required=True)