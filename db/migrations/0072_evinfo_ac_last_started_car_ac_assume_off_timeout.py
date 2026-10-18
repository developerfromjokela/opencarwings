import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0071_crmtroublerecord_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='evinfo',
            name='ac_last_started',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='car',
            name='ac_assume_off_timeout',
            field=models.IntegerField(default=0),
        ),
    ]
