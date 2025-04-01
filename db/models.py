import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core import validators
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.utils.translation import gettext_lazy as _

ALERT_TYPES = (
    (1, 'Charge stop'),
    (2, 'Charge start'),
    (3, 'Charge cable reminder'),
    (4, 'A/C on'),
    (5, 'A/C off'),
    (6, 'Configuration read'),
    (7, 'A/C auto off'),
    (96, 'Charge error'),
    (97, 'A/C error'),
    (98, 'Command timeout'),
    (99, 'Error')
)

COMMAND_TYPES = (
    (0, 'No command'),
    (1, 'Refresh data'),
    (2, 'Charge start'),
    (3, 'A/C on'),
    (4, 'A/C off'),
    (5, 'Read configuration')
)

COMMAND_RESULTS = (
    (-1, 'Waiting'),
    (0, 'Success'),
    (1, 'Error'),
    (2, 'Timeout'),
    (3, 'Await response')
)

CAR_GEAR = (
    (0, "Park"),
    (1, "Drive"),
    (2, "Reverse")
)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

class CARWINGSUsernameValidator(validators.RegexValidator):
    regex = r"^[A-Za-z0-9\-_\.]+\Z"
    message = _(
        "Enter a valid username. This value may contain only unaccented lowercase a-z "
        "and uppercase A-Z letters, numbers, and /./-/_ characters."
    )
    flags = re.ASCII

class CARWINGSPasswordValidator(validators.RegexValidator):
    regex = r"^[A-Za-z0-9\-_=+@#?!]+\Z"
    message = _(
        "Enter a valid TCU Password. This value may contain only unaccented lowercase a-z "
        "and uppercase A-Z letters, numbers, and /=/-/_/+/@/#/?/! characters."
    )
    flags = re.ASCII

# Username: only AA-ZZ aa-zz 0-9 - _ .
# password: only AA-ZZ aa-zz 0-9 - _ = + @ # ? !
class User(AbstractUser):
    username_validator = CARWINGSUsernameValidator()
    tcu_pass_validator = CARWINGSPasswordValidator()
    tcu_pass_hash = models.CharField(max_length=16, validators=[tcu_pass_validator])
    username = models.CharField(
        _("username"),
        max_length=16,
        unique=True,
        help_text=_(
            "Required. 16 characters or fewer. Letters, digits and /./-/_ only."
        ),
        validators=[username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    email_notifications = models.BooleanField(default=True)


class TCUConfiguration(models.Model):
    dial_code = models.CharField(max_length=10, default=None, null=True, blank=True)
    apn = models.CharField(max_length=48, default=None, null=True, blank=True)
    apn_user = models.CharField(max_length=32, default=None, null=True, blank=True)
    apn_password = models.CharField(max_length=32, default=None, null=True, blank=True)
    dns1 = models.CharField(max_length=32, default=None, null=True, blank=True)
    dns2 = models.CharField(max_length=32, default=None, null=True, blank=True)
    server_url = models.CharField(max_length=128, default=None, null=True, blank=True)
    proxy_url = models.CharField(max_length=128, default=None, null=True, blank=True)
    connection_type = models.CharField(max_length=3, default=None, null=True, blank=True)
    last_updated = models.DateTimeField(null=True, default=None, blank=True)

class LocationInfo(models.Model):
    lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, default=None, blank=True)
    lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, default=None, blank=True)
    home = models.BooleanField(default=False)
    last_updated = models.DateTimeField(null=True, default=None, blank=True)

class EVInfo(models.Model):
    range_acon = models.IntegerField(default=0, null=True, blank=True)
    range_acoff = models.IntegerField(default=0, null=True, blank=True)
    plugged_in = models.BooleanField(default=False)
    charging = models.BooleanField(default=False)
    ac_status = models.BooleanField(default=False)
    charge_bars = models.IntegerField(default=0)
    car_running = models.BooleanField(default=False)
    car_gear = models.IntegerField(default=0, choices=CAR_GEAR)
    eco_mode = models.BooleanField(default=False)
    soh = models.IntegerField(default=0)
    soc = models.IntegerField(default=0)
    soc_display = models.IntegerField(default=0)
    cap_bars = models.IntegerField(default=0)
    gids = models.IntegerField(default=0)
    gids_relative = models.IntegerField(default=0)
    max_gids_relative = models.IntegerField(default=0)
    full_chg_time = models.IntegerField(default=0)
    limit_chg_time = models.IntegerField(default=0)
    last_updated = models.DateTimeField(null=True, default=None, blank=True)

class AlertHistory(models.Model):
    type = models.IntegerField(choices=ALERT_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    command_id = models.IntegerField(default=None, null=True)
    additional_data = models.TextField(null=True, default=None)
    car = models.ForeignKey('Car', on_delete=models.CASCADE)

class Car(models.Model):
    vin = models.CharField(max_length=18, unique=True)
    nickname = models.CharField(max_length=64, default="LEAF")
    sms_config = models.JSONField()
    vehicle_code1 = models.IntegerField(default=0)
    vehicle_code2 = models.IntegerField(default=0)
    vehicle_code3 = models.IntegerField(default=0)
    vehicle_code4 = models.IntegerField(default=0)
    tcu_model = models.CharField(max_length=32, null=True, default=None)
    tcu_serial = models.CharField(max_length=32, null=True, default=None)
    iccid = models.CharField(max_length=32, null=True, default=None)
    tcu_ver = models.CharField(max_length=32, null=True, default=None, blank=True)
    tcu_user = models.CharField(max_length=16, null=True, default=None, blank=True)
    tcu_pass = models.CharField(max_length=16, null=True, default=None, blank=True)
    disable_auth = models.BooleanField(default=False)
    last_connection = models.DateTimeField(null=True, default=None, blank=True)
    tcu_configuration = models.OneToOneField(TCUConfiguration, on_delete=models.CASCADE)
    location = models.OneToOneField(LocationInfo, on_delete=models.CASCADE)
    ev_info = models.OneToOneField(EVInfo, on_delete=models.CASCADE)
    # Command handle
    command_id = models.IntegerField(default=-1)
    command_result = models.IntegerField(default=-1, choices=COMMAND_RESULTS)
    command_requested = models.BooleanField(default=False)
    command_payload = models.JSONField(null=True, default=None, blank=True)
    command_type = models.IntegerField(choices=COMMAND_TYPES, default=0)
    command_request_time = models.DateTimeField(null=True, default=None, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)