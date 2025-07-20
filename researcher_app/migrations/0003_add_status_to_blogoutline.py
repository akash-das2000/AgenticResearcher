from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0002_add_title_to_blogoutline'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogoutline',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('drafting', 'Editing Outline'),
                    ('finalized', 'Outline Finalized'),
                ],
                default='drafting',
                help_text='Have we locked in the outline yet?'
            ),
        ),
    ]
