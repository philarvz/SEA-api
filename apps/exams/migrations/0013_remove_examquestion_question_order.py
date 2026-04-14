from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0012_alter_exam_creation_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='examquestion',
            name='question_order',
        ),
        migrations.AlterModelOptions(
            name='examquestion',
            options={
                'ordering': ['id_exam', 'id_exam_question'],
                'verbose_name': 'Exam Question',
                'verbose_name_plural': 'Exam Questions',
            },
        ),
    ]
