# Generated by Django 4.2.1 on 2023-06-18 22:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_invitation_approved'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invitation',
            name='send_invite',
        ),
    ]
