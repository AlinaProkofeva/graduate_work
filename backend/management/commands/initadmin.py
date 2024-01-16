from django.core.management.base import BaseCommand
import os
from backend.models import User
from dotenv import load_dotenv


load_dotenv()


class Command(BaseCommand):
    """
    Создание первого суперпользователя для входа в админ-панель при запуске проекта в docker-контейнере.
    """

    def handle(self, *args, **options):
        if User.objects.count() == 0:
            email = os.getenv('TEST_SUPERUSER_EMAIL')
            password = os.getenv('TEST_SUPERUSER_PASSWORD')
            print(f'Creating account for {email}')
            admin = User.objects.create_superuser(email=email, password=password)
            admin.is_active = True
            admin.is_admin = True
            admin.save()
        else:
            print('Admin accounts can only be initialized if no Accounts exist')
