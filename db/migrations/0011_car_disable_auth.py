# Generated by Django 5.1.7 on 2025-04-01 16:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0010_alter_user_tcu_pass_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='car',
            name='disable_auth',
            field=models.BooleanField(default=False),
        ),
    ]
