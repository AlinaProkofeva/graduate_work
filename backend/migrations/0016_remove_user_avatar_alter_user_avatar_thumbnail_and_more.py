# Generated by Django 4.1.3 on 2024-01-31 11:27

import backend.models
from django.db import migrations, models
import django.db.models.deletion
import imagekit.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0015_user_avatar_thumbnail_alter_user_avatar'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='avatar',
        ),
        migrations.AlterField(
            model_name='user',
            name='avatar_thumbnail',
            field=imagekit.models.fields.ProcessedImageField(blank=True, default='ava_thumbnails/default.jpg', upload_to=backend.models.upload_ava_thumbnail_location, verbose_name='Аватар'),
        ),
        migrations.CreateModel(
            name='ProductInfoPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', imagekit.models.fields.ProcessedImageField(blank=True, upload_to='images/%Y/%m/%d', verbose_name='Изображение')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='backend.productinfo', verbose_name='Товар')),
            ],
        ),
    ]