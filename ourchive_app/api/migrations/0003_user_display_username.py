# Generated by Django 4.2.1 on 2023-06-09 16:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_user_can_upload_audio_user_can_upload_images_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='display_username',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
