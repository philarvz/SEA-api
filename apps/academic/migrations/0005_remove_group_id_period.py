from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0004_audit_fields_datetime'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='id_period',
        ),
    ]
