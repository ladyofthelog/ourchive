# Generated by Django 4.2.4 on 2023-09-02 21:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0045_rename_homepage_include_tagtype_filterable'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookmarkcollection',
            name='works',
            field=models.ManyToManyField(to='api.work'),
        ),
    ]
