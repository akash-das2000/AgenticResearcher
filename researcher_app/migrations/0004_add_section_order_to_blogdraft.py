from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0003_add_status_to_blogoutline'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogdraft',
            name='section_order',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Order of this section within the outline'
            ),
        ),
    ]
