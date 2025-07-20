# researcher_app/migrations/0006_create_feedback_model.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0006_add_author_name_to_blogoutline'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_order', models.PositiveIntegerField(
                    null=True, blank=True,
                    help_text='Which section this feedback applies to (or null for outline)'
                )),
                ('text', models.TextField(
                    help_text='What the user asked to tweak'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('outline', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feedbacks',
                    to='researcher_app.blogoutline'
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
