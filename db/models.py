import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core import validators
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.utils.translation import gettext_lazy as _

ALERT_TYPES = (
    (1, _('Charge stop')),
    (2, _('Charge start')),
    (3, _('Charge cable reminder')),
    (4, _('A/C on')),
    (5, _('A/C off')),
    (6, _('Configuration read')),
    (7, _('A/C auto off')),
    (8, _("Quick charge stop")),
    (96, _('Charge error')),
    (97, _('A/C error')),
    (98, _('Command timeout')),
    (99, _('Error'))
)

COMMAND_TYPES = (
    (0, _('No command')),
    (1, _('Refresh data')),
    (2, _('Charge start')),
    (3, _('A/C on')),
    (4, _('A/C off')),
    (5, _('Read configuration'))
)

COMMAND_RESULTS = (
    (-1, _('Waiting')),
    (0, _('Success')),
    (1, _('Error')),
    (2, _('Timeout')),
    (3, _('Await response'))
)

CAR_GEAR = (
    (0, _("Park")),
    (1, _("Drive")),
    (2, _("Reverse"))
)

PERIODIC_REFRESH = (
    (0, _("Never")),
    (30, _("Every 30 minutes")),
    (45, _("Every 45 minutes")),
    (60, _("Every hour")),
    (180, _("Every three hours")),
    (720, _("Every 12 hours")),
    (1440, _("Every day"))
)

PERIODIC_REFRESH_ACTIVE = (
    (0, _("Never")),
    (5, _("Every 5 minutes")),
    (15, _("Every 15 minutes")),
    (30, _("Every 30 minutes")),
    (45, _("Every 45 minutes")),
    (60, _("Every hour")),
    (180, _("Every three hours")),
    (720, _("Every 12 hours")),
    (1440, _("Every day"))
)

CAR_COLOR = (
    ("l_coulisred", "LEAF Coulis Red"),
    ("l_deepblue", "LEAF Deep Blue"),
    ("l_forgedbronze", "LEAF Forged Bronze"),
    ("l_gunmetallic", "LEAF Gun Metallic"),
    ("l_pearlwhite", "LEAF Pearl White"),
    ("l_planetblue", "LEAF Planet Blue"),
    ("l_superblack", "LEAF Super Black"),
    ("env200_white", "e-NV200 White"),
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
    charge_finish = models.BooleanField(default=False)
    quick_charging = models.BooleanField(default=False)
    ac_status = models.BooleanField(default=False)
    charge_bars = models.IntegerField(default=0)
    car_running = models.BooleanField(default=False)
    car_gear = models.IntegerField(default=0, choices=CAR_GEAR)
    eco_mode = models.BooleanField(default=False)
    soh = models.IntegerField(default=0)
    soc = models.FloatField(default=0)
    soc_display = models.FloatField(default=0)
    wh_content = models.FloatField(default=0)
    cap_bars = models.IntegerField(default=0)
    gids = models.IntegerField(default=0)
    counter = models.IntegerField(default=0)
    max_gids = models.IntegerField(default=0)
    full_chg_time = models.IntegerField(default=0)
    limit_chg_time = models.IntegerField(default=0)
    obc_6kw = models.IntegerField(default=0)
    param21 = models.IntegerField(default=0)
    force_soc_display = models.BooleanField(default=False)
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
    color = models.TextField(choices=CAR_COLOR, default=CAR_COLOR[0])
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
    disable_auth = models.BooleanField(default=True)
    last_connection = models.DateTimeField(null=True, default=None, blank=True)
    tcu_configuration = models.OneToOneField(TCUConfiguration, on_delete=models.CASCADE)
    location = models.OneToOneField(LocationInfo, on_delete=models.CASCADE)
    ev_info = models.OneToOneField(EVInfo, on_delete=models.CASCADE)
    periodic_refresh = models.IntegerField(default=0, choices=PERIODIC_REFRESH)
    periodic_refresh_running = models.IntegerField(default=0, choices=PERIODIC_REFRESH_ACTIVE)
    # Command handle
    command_id = models.IntegerField(default=-1)
    command_result = models.IntegerField(default=-1, choices=COMMAND_RESULTS)
    command_requested = models.BooleanField(default=False)
    command_payload = models.JSONField(null=True, default=None, blank=True)
    command_type = models.IntegerField(choices=COMMAND_TYPES, default=0)
    command_request_time = models.DateTimeField(null=True, default=None, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)