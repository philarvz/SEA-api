from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('exams', '0013_remove_examquestion_question_order'),
        ('questions', '0005_question_bank_extensions'),
        ('users', '0002_alter_user_matricula_passwordresetcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentAnswer',
            fields=[
                ('modified_at', models.DateTimeField(auto_now=True, blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, blank=True, null=True)),
                ('id_student_answer', models.AutoField(db_column='id_student_answer', primary_key=True, serialize=False)),
                ('answer_text', models.TextField(blank=True, db_column='answer_text', null=True)),
                ('code_answer', models.TextField(blank=True, db_column='code_answer', null=True)),
                ('is_correct', models.BooleanField(blank=True, db_column='is_correct', null=True)),
                ('score', models.DecimalField(blank=True, db_column='score', decimal_places=2, max_digits=6, null=True)),
                ('evaluated_at', models.DateTimeField(blank=True, db_column='evaluated_at', null=True)),
                ('exam_assignment', models.ForeignKey(db_column='exam_assignment_id', on_delete=django.db.models.deletion.CASCADE, related_name='student_answers', to='exams.examassignment')),
                ('modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_modified_by_set', to='users.user')),
                ('question', models.ForeignKey(db_column='id_question', on_delete=django.db.models.deletion.CASCADE, related_name='student_answers', to='questions.question')),
                ('selected_answer', models.ForeignKey(blank=True, db_column='selected_answer_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='selected_in_student_answers', to='questions.answer')),
                ('selected_answers', models.ManyToManyField(blank=True, related_name='multi_selected_in_student_answers', to='questions.answer')),
            ],
            options={
                'verbose_name': 'Student Answer',
                'verbose_name_plural': 'Student Answers',
                'db_table': 'student_answer',
                'ordering': ['-id_student_answer'],
                'unique_together': {('exam_assignment', 'question')},
            },
        ),
    ]
