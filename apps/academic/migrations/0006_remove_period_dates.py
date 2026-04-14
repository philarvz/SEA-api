# Generated migration for Period model changes

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0005_remove_group_id_period'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='period',
            name='start_date',
        ),
        migrations.RemoveField(
            model_name='period',
            name='end_date',
        ),
    ]
