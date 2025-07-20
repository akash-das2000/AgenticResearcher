from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('researcher_app', '0004_add_section_order_to_blogdraft'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogdraft',
            name='is_final',
            field=models.BooleanField(
                default=False,
                help_text='True once the user has “OK’d” this section'
            ),
        ),
    ]
