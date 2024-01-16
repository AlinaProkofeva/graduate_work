import os
from celery import Celery
from django.conf import settings


# Указываем, где находится модуль django и файл с настройками django (имя_вашего_проекта.settings)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_site.settings')

app = Celery('shop_site', broker=os.getenv('BROKER'), backend=os.getenv('BACKEND'))
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(settings.INSTALLED_APPS)

BROKER_URL = os.getenv('BROKER')
broker_url = os.getenv('BROKER')
app.conf.broker_url = BROKER_URL
CELERY_BROKER_URL = BROKER_URL

if __name__ == '__main__':
    app.start()
