from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a default superuser if none exist'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        username = os.getenv('DJANGO_ADMIN_USERNAME', 'admin')
        email = os.getenv('DJANGO_ADMIN_EMAIL', 'admin@example.com')
        password = os.getenv('DJANGO_ADMIN_PASSWORD', 'adminpassword')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'✅ Superuser created: {username}/{password}'))
        else:
            self.stdout.write(self.style.WARNING('⚠️ Superuser already exists. Skipping.'))
