# Generated by Django 4.2.4 on 2023-08-05 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_tag_created_on_tag_updated_on'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentpage',
            name='locked_to_users',
            field=models.BooleanField(default=False),
        ),
    ]
