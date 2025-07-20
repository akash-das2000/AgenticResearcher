from django.db import migrations

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('researcher_app', '__first__'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='blogoutline',
            name='user',
        ),
    ]
