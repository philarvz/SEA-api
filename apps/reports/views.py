from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from apps.academic.permissions import IsTeacherOrAdmin
from .services import ReportService
from .serializers import (
    ByExamSerializer,
    ByGroupSerializer,
    ByStudentSerializer,
    StudentExamDetailSerializer
)


class ByExamView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        request=ByExamSerializer,
        responses={200: dict},
        description="Reporte por examen"
    )
    def post(self, request):
        serializer = ByExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = ReportService.by_exam(serializer.validated_data)

        return Response({"success": True, "data": data})


class ByGroupView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        request=ByGroupSerializer,
        responses={200: dict},
        description="Reporte por grupo"
    )
    def post(self, request):
        serializer = ByGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = ReportService.by_group(serializer.validated_data)

        return Response({"success": True, "data": data})


class ByStudentView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        request=ByStudentSerializer,
        responses={200: dict},
        description="Reporte por alumno"
    )
    def post(self, request):
        serializer = ByStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = ReportService.by_student(serializer.validated_data)

        return Response({"success": True, "data": data})


class StudentExamDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(
        request=StudentExamDetailSerializer,
        responses={200: dict},
        description="Detalle alumno-examen"
    )
    def post(self, request):
        serializer = StudentExamDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = ReportService.student_exam_detail(serializer.validated_data)

        return Response({"success": True, "data": data})