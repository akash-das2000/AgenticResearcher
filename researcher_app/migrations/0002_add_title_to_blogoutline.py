from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0001_initial'),
    ]

    operations = [
        # migrations.AddField(
        #     model_name='blogoutline',
        #     name='title',
        #     field=models.CharField(
        #         max_length=200,
        #         blank=True,
        #         default='',
        #         help_text='Final blog title (filled in when ready)'
        #     ),
        # ),
        # No-op: 'title' already exists in 0001_initial
    ]
