# Generated by Django 4.1.3 on 2024-01-10 19:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0009_alter_address_options_alter_contact_user_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='address',
            options={'verbose_name': 'Адрес пользователя', 'verbose_name_plural': 'Адреса пользователя'},
        ),
    ]
