# Generated by Django 5.0.1 on 2025-01-15 14:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_sitesettings'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='joined_date',
        ),
    ]
