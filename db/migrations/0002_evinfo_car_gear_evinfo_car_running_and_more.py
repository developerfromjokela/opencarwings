# Generated by Django 5.1.7 on 2025-03-27 15:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evinfo',
            name='car_gear',
            field=models.IntegerField(choices=[(0, 'Park'), (1, 'Drive'), (2, 'Reverse')], default=0),
        ),
        migrations.AddField(
            model_name='evinfo',
            name='car_running',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='evinfo',
            name='charge_bars',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='evinfo',
            name='eco_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='evinfo',
            name='soc',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='evinfo',
            name='soh',
            field=models.IntegerField(default=0),
        ),
    ]
