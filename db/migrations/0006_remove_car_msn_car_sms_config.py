# Generated by Django 5.1.7 on 2025-03-28 21:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0005_alter_car_command_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='car',
            name='msn',
        ),
        migrations.AddField(
            model_name='car',
            name='sms_config',
            field=models.JSONField(default='{"provider": "manual"}'),
            preserve_default=False,
        ),
    ]
