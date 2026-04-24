from django.db import models


class VwExamAssignmentDetail(models.Model):
    """
    Unmanaged model mapped to the vw_exam_assignment_detail database view.
    Pre-joins exam_assignment ↔ exam ↔ subject ↔ student ↔ group ↔ generation ↔ teacher.
    """
    assignment_id = models.IntegerField(primary_key=True)
    exam_id = models.IntegerField()
    exam_name = models.CharField(max_length=200)
    exam_title = models.CharField(max_length=200)
    difficulty_level = models.CharField(max_length=20)
    exam_active = models.BooleanField()
    exam_creation_date = models.DateTimeField()

    id_subject = models.IntegerField()
    subject_name = models.CharField(max_length=150)
    subject_level = models.IntegerField()

    student_id = models.IntegerField()
    student_first_name = models.CharField(max_length=150)
    student_last_name = models.CharField(max_length=150)
    student_email = models.EmailField()
    student_matricula = models.CharField(max_length=20, null=True)

    group_id = models.IntegerField()
    group_letter = models.CharField(max_length=1)
    academic_level = models.IntegerField()
    generation_year = models.IntegerField()

    assignment_status = models.CharField(max_length=20)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    is_passed = models.BooleanField(null=True)
    assigned_at = models.DateTimeField()
    available_from = models.DateTimeField()
    available_to = models.DateTimeField()
    attempt_date = models.DateTimeField(null=True)

    teacher_id = models.IntegerField()
    teacher_first_name = models.CharField(max_length=150)
    teacher_last_name = models.CharField(max_length=150)

    class Meta:
        managed = False
        db_table = 'vw_exam_assignment_detail'
        ordering = ['-assigned_at']


class VwExamGroupStats(models.Model):
    """
    Unmanaged model mapped to the vw_exam_group_stats database view.
    Pre-aggregated per-exam/group statistics.
    """
    exam_id = models.IntegerField(primary_key=True)
    exam_name = models.CharField(max_length=200)
    exam_title = models.CharField(max_length=200)
    group_id = models.IntegerField()
    group_letter = models.CharField(max_length=1)
    academic_level = models.IntegerField()
    generation_year = models.IntegerField()

    total_students = models.IntegerField()
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    pending_count = models.IntegerField()
    in_progress_count = models.IntegerField()
    completed_count = models.IntegerField()
    approved_count = models.IntegerField()
    scored_count = models.IntegerField()
    approval_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'vw_exam_group_stats'
