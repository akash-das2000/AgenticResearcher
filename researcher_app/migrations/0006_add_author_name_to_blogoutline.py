from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0005_add_is_final_to_blogdraft'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogoutline',
            name='author_name',
            field=models.CharField(blank=True, default='', help_text='Author name for the blog', max_length=100),
        ),
    ]
