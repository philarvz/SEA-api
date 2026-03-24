from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_add_matricula_and_teacher_subjects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='matricula',
            field=models.CharField(
                db_column='matricula',
                help_text='Matrícula institucional única del usuario.',
                max_length=20,
                unique=True,
            ),
        ),
    ]
