FROM python:3.11-slim

WORKDIR /code
RUN mkdir /code/static

ADD . .

RUN pip install -r requirements.txt

# обновляем устаревший файл до работоспособности, чтобы он не ронял makemigrations при попытке импортировать url из
# django.conf.urls
RUN rm /usr/local/lib/python3.11/site-packages/rest_framework_social_oauth2/urls.py
COPY docker/rest_framework_social_oauth2/urls.py /usr/local/lib/python3.11/site-packages/rest_framework_social_oauth2

# добавляем описание авторизации через ВК для сваггера
RUN rm /usr/local/lib/python3.11/site-packages/rest_framework_social_oauth2/views.py
COPY docker/rest_framework_social_oauth2/views.py /usr/local/lib/python3.11/site-packages/rest_framework_social_oauth2

# убираем лишние административные таблицы, которые не используются при настройке
RUN rm /usr/local/lib/python3.11/site-packages/social_django/admin.py
COPY docker/social_django/admin.py /usr/local/lib/python3.11/site-packages/social_django
RUN rm /usr/local/lib/python3.11/site-packages/oauth2_provider/admin.py
COPY docker/oauth2_provider/admin.py /usr/local/lib/python3.11/site-packages/oauth2_provider

RUN python manage.py makemigrations