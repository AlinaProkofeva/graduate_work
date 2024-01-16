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

RUN python manage.py makemigrations