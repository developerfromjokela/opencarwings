# Generated by Django 5.1.7 on 2025-04-24 13:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0016_evinfo_charge_finish'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evinfo',
            name='soc',
            field=models.FloatField(default=0),
        ),
    ]
