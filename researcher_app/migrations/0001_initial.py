from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UploadedPDF',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='uploads/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ExtractedContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('images', models.JSONField(default=list)),
                ('tables', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pdf', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='content', to='researcher_app.uploadedpdf')),
            ],
        ),
        migrations.CreateModel(
            name='BlogOutline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, help_text='Final blog title (filled in when ready)', max_length=200)),
                ('outline_json', models.JSONField()),
                ('status', models.CharField(choices=[('drafting','Editing Outline'),('finalized','Outline Finalized')], default='drafting', max_length=20, help_text='Have we locked in the outline yet?')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pdf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outlines', to='researcher_app.uploadedpdf')),
            ],
        ),
        migrations.CreateModel(
            name='BlogDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_order', models.PositiveIntegerField(help_text='Order of this section within the outline')),
                ('section_title', models.CharField(max_length=255)),
                ('content', models.TextField(help_text='Current draft of the section')),
                ('is_final', models.BooleanField(default=False, help_text='True once the user has ‘OK’d’ this section')),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('outline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drafts', to='researcher_app.blogoutline')),
            ],
            options={
                'ordering': ['section_order'],
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_message', models.TextField()),
                ('agent_response', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('pdf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chats', to='researcher_app.uploadedpdf')),
            ],
        ),
        migrations.CreateModel(
            name='NormalizationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_name', models.CharField(max_length=255)),
                ('pattern', models.CharField(max_length=500)),
                ('replacement', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
