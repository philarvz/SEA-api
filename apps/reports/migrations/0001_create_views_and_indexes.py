"""
Migration: Create database views and indexes for the SEA system.

Views:
  - vw_exam_assignment_detail: Pre-joins exam_assignment with student, exam, subject, group.
  - vw_exam_group_stats: Pre-aggregated per-exam/group statistics.

Indexes (on critical query paths only):
  - idx_exam_assignment_exam_status: exam_assignment(exam_id, status)
  - idx_exam_assignment_student: exam_assignment(student_id)
  - idx_student_answer_assignment: student_answer(exam_assignment_id)
  - idx_question_subject_difficulty: question(id_subject, difficulty)
  - idx_audit_log_table_changed: audit_log(table_name, changed_at)
"""

from django.db import migrations


# ── Vista 1: Detalle completo de asignaciones de examen ──────────────────
CREATE_VIEW_EXAM_ASSIGNMENT_DETAIL = """
CREATE OR REPLACE VIEW vw_exam_assignment_detail AS
SELECT
    ea.id                AS assignment_id,
    ea.exam_id,
    e.name               AS exam_name,
    e.title              AS exam_title,
    e.difficulty_level,
    e.status             AS exam_active,
    e.creation_date      AS exam_creation_date,
    s.id_subject,
    s.name               AS subject_name,
    s.level_number       AS subject_level,
    ea.student_id,
    u.first_name         AS student_first_name,
    u.last_name          AS student_last_name,
    u.email              AS student_email,
    u.matricula          AS student_matricula,
    ea.group_id,
    g.group_letter,
    g.academic_level,
    gen.year             AS generation_year,
    ea.status            AS assignment_status,
    ea.score,
    ea.is_passed,
    ea.assigned_at,
    ea.available_from,
    ea.available_to,
    ea.attempt_date,
    e.id_teacher         AS teacher_id,
    t.first_name         AS teacher_first_name,
    t.last_name          AS teacher_last_name
FROM exam_assignment ea
JOIN exam e            ON e.id_exam      = ea.exam_id
JOIN subject s         ON s.id_subject   = e.id_subject
JOIN "user" u          ON u.id_user      = ea.student_id
JOIN "group" g         ON g.id_group     = ea.group_id
JOIN generation gen    ON gen.id_generation = g.id_generation
JOIN "user" t          ON t.id_user      = e.id_teacher;
"""

DROP_VIEW_EXAM_ASSIGNMENT_DETAIL = """
DROP VIEW IF EXISTS vw_exam_assignment_detail;
"""


# ── Vista 2: Estadísticas agregadas por examen y grupo ───────────────────
CREATE_VIEW_EXAM_GROUP_STATS = """
CREATE OR REPLACE VIEW vw_exam_group_stats AS
SELECT
    ea.exam_id,
    e.name                                       AS exam_name,
    e.title                                      AS exam_title,
    ea.group_id,
    g.group_letter,
    g.academic_level,
    gen.year                                     AS generation_year,
    COUNT(*)                                     AS total_students,
    ROUND(AVG(ea.score), 2)                      AS average_score,
    MAX(ea.score)                                AS highest_score,
    MIN(ea.score)                                AS lowest_score,
    COUNT(*) FILTER (WHERE ea.status = 'pending')     AS pending_count,
    COUNT(*) FILTER (WHERE ea.status = 'in_progress') AS in_progress_count,
    COUNT(*) FILTER (WHERE ea.status = 'completed')   AS completed_count,
    COUNT(*) FILTER (WHERE ea.score >= e.minimum_score
                       AND ea.score IS NOT NULL)      AS approved_count,
    COUNT(*) FILTER (WHERE ea.score IS NOT NULL)      AS scored_count,
    CASE
        WHEN COUNT(*) FILTER (WHERE ea.score IS NOT NULL) > 0
        THEN ROUND(
            COUNT(*) FILTER (WHERE ea.score >= e.minimum_score AND ea.score IS NOT NULL)::numeric
            / COUNT(*) FILTER (WHERE ea.score IS NOT NULL)::numeric * 100, 2
        )
        ELSE NULL
    END                                           AS approval_rate
FROM exam_assignment ea
JOIN exam e          ON e.id_exam      = ea.exam_id
JOIN "group" g       ON g.id_group     = ea.group_id
JOIN generation gen  ON gen.id_generation = g.id_generation
GROUP BY ea.exam_id, e.id_exam, e.name, e.title, e.minimum_score,
         ea.group_id, g.group_letter, g.academic_level, gen.year;
"""

DROP_VIEW_EXAM_GROUP_STATS = """
DROP VIEW IF EXISTS vw_exam_group_stats;
"""


# ── Índices sobre datos críticos ─────────────────────────────────────────
CREATE_INDEXES = """
-- Reportes por examen + filtrado por status (by_exam, get_group_stats, finalize)
CREATE INDEX IF NOT EXISTS idx_exam_assignment_exam_status
    ON exam_assignment (exam_id, status);

-- Reportes por estudiante (by_student, get_student_assignments)
CREATE INDEX IF NOT EXISTS idx_exam_assignment_student
    ON exam_assignment (student_id);

-- Calificación: respuestas por asignación (grading_service, answer listing)
CREATE INDEX IF NOT EXISTS idx_student_answer_assignment
    ON student_answer (exam_assignment_id);

-- Banco de preguntas: filtrado por materia y dificultad
CREATE INDEX IF NOT EXISTS idx_question_subject_difficulty
    ON question (id_subject, difficulty);

-- Auditoría: filtrado por tabla y rango de fechas
CREATE INDEX IF NOT EXISTS idx_audit_log_table_changed
    ON audit_log (table_name, changed_at);
"""

DROP_INDEXES = """
DROP INDEX IF EXISTS idx_exam_assignment_exam_status;
DROP INDEX IF EXISTS idx_exam_assignment_student;
DROP INDEX IF EXISTS idx_student_answer_assignment;
DROP INDEX IF EXISTS idx_question_subject_difficulty;
DROP INDEX IF EXISTS idx_audit_log_table_changed;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0013_remove_examquestion_question_order'),
        ('questions', '0005_question_bank_extensions'),
        ('audit', '0001_initial'),
    ]

    operations = [
        # Vistas
        migrations.RunSQL(
            sql=CREATE_VIEW_EXAM_ASSIGNMENT_DETAIL,
            reverse_sql=DROP_VIEW_EXAM_ASSIGNMENT_DETAIL,
        ),
        migrations.RunSQL(
            sql=CREATE_VIEW_EXAM_GROUP_STATS,
            reverse_sql=DROP_VIEW_EXAM_GROUP_STATS,
        ),
        # Índices
        migrations.RunSQL(
            sql=CREATE_INDEXES,
            reverse_sql=DROP_INDEXES,
        ),
    ]
