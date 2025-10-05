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
    (9, _('Battery heater start')),
    (10, _('Battery heater stop')),
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
    (10, _("Every 10 minutes")),
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

CHARGE_TYPES = (
    (1, _("Slow charge")),
    (2, _("Quick charge")),
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
    units_imperial = models.BooleanField(default=False)


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

class SendToCarLocation(models.Model):
    lat = models.DecimalField(max_digits=20, decimal_places=10)
    lon = models.DecimalField(max_digits=20, decimal_places=10)
    name = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

class RoutePlan(models.Model):
    name = models.CharField(max_length=31)
    created_at = models.DateTimeField(auto_now_add=True)
    #start
    start_name = models.CharField(max_length=30)
    start_lat = models.DecimalField(max_digits=20, decimal_places=10)
    start_lon = models.DecimalField(max_digits=20, decimal_places=10)
    #finish
    finish_name = models.CharField(max_length=30)
    finish_lat = models.DecimalField(max_digits=20, decimal_places=10)
    finish_lon = models.DecimalField(max_digits=20, decimal_places=10)
    # waypoint 1
    point1_name = models.CharField(max_length=30, blank=True, null=True)
    point1_lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    point1_lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    # waypoint 2
    point2_name = models.CharField(max_length=30, blank=True, null=True)
    point2_lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    point2_lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    # waypoint 3
    point3_name = models.CharField(max_length=30, blank=True, null=True)
    point3_lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    point3_lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    # waypoint 4
    point4_name = models.CharField(max_length=30, blank=True, null=True)
    point4_lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    point4_lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    # waypoint 5
    point5_name = models.CharField(max_length=30, blank=True, null=True)
    point5_lat = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    point5_lon = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)


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
    color = models.TextField(choices=CAR_COLOR, default="l_planetblue")
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
    # CarWings navi
    send_to_car_location = models.ManyToManyField(SendToCarLocation)
    route_plans = models.ManyToManyField(RoutePlan)
    carrier = models.CharField(max_length=64, null=True, default=None)
    signal_level = models.IntegerField(default=-1)
    odometer = models.IntegerField(default=-1)
    navi_version = models.CharField(max_length=64, null=True, default=None, blank=True)
    map_version = models.CharField(max_length=64, null=True, default=None, blank=True)
    tcu_version = models.CharField(max_length=64, null=True, default=None, blank=True)
    favorite_channels = models.JSONField(default=dict)
    custom_channels = models.JSONField(default=dict)


# Probe data

## Probe CRM
class CRMLatest(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    phone_contacts = models.IntegerField(default=0)
    navi_points_saved = models.IntegerField(default=0)
    odometer = models.IntegerField(default=0)
    last_updated = models.DateTimeField(null=True, default=None, blank=True)

class CRMLifetime(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    aircon_usage = models.BigIntegerField(default=0)
    headlight_on_time = models.BigIntegerField(default=0)
    average_speed = models.FloatField(default=0)
    regen = models.BigIntegerField(default=0)
    consumption = models.BigIntegerField(default=0)
    running_time = models.BigIntegerField(default=0)
    mileage = models.FloatField(default=0)
    last_updated = models.DateTimeField(null=True, default=None, blank=True)

class CRMExcessiveAirconRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start = models.DateTimeField()
    consumption = models.BigIntegerField(default=0)

class CRMExcessiveIdlingRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start = models.DateTimeField()
    duration = models.BigIntegerField(default=0)

class CRMMonthlyRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start = models.DateTimeField()
    end = models.DateTimeField()
    distance = models.FloatField(default=0)
    drive_time = models.BigIntegerField(default=0)
    average_speed = models.FloatField(default=0)
    p_range_freq = models.BigIntegerField(default=0)
    r_range_freq = models.BigIntegerField(default=0)
    n_range_freq = models.BigIntegerField(default=0)
    b_range_freq = models.BigIntegerField(default=0)
    trip_count = models.IntegerField(default=0)
    braking_speeds = models.JSONField(default=list)
    start_stop_distances = models.JSONField(default=list)
    regen_total_wh = models.BigIntegerField(default=0)
    consumed_total_wh = models.BigIntegerField(default=0)
    average_accel = models.FloatField(default=0)
    switch_usage_parked = models.JSONField(default=list)
    switch_usage_driving = models.JSONField(default=list)

class CRMMSNRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    data = models.JSONField()

class CRMChargeRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    charge_count = models.IntegerField(default=0)
    charge_type = models.IntegerField(default=0, choices=CHARGE_TYPES)
    charger_position_latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    charger_position_longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)

class CRMChargeHistoryRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    charge_bars_start = models.IntegerField(default=0)
    charge_bars_end = models.IntegerField(default=0)
    gids_start = models.IntegerField(default=0)
    gids_end = models.IntegerField(default=0)
    power_consumption = models.IntegerField(default=0)
    charging_type = models.IntegerField(default=0, choices=CHARGE_TYPES)
    latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    #temp st
    batt_avg_temp_start = models.IntegerField(default=0)
    batt_max_temp_start = models.IntegerField(default=0)
    batt_min_temp_start = models.IntegerField(default=0)
    #temp end
    batt_avg_temp_end = models.IntegerField(default=0)
    batt_max_temp_end = models.IntegerField(default=0)
    batt_min_temp_end = models.IntegerField(default=0)
    #cellvolt
    batt_avg_cell_volt_start = models.IntegerField(default=0)
    batt_max_cell_volt_start = models.IntegerField(default=0)
    batt_min_cell_volt_start = models.IntegerField(default=0)
    current_accumulation_start = models.IntegerField(default=0)
    charges_while_ignoff = models.IntegerField(default=0)

class CRMABSHistoryRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    operation_time = models.IntegerField(default=0)
    vehicle_speed_start = models.IntegerField(default=0)
    vehicle_speed_end = models.IntegerField(default=0)
    latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    road_type = models.IntegerField(default=0)
    direction = models.IntegerField(default=0)

class CRMDistanceRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    consumed_wh = models.IntegerField(default=0)
    regenerated_wh = models.IntegerField(default=0)
    latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    road_type = models.IntegerField(default=0)

class CRMTroubleRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    data = models.JSONField()

class CRMTripRecord(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start_ts = models.DateTimeField()
    end_ts = models.DateTimeField()
    start_latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    start_longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    end_latitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    end_longitude = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    distance = models.FloatField(default=0)
    sudden_accelerations = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    sudden_decelerations = models.DecimalField(default=0, decimal_places=15, max_digits=32)
    highway_optimal_speed_time = models.BigIntegerField(default=0)
    aircon_usage = models.BigIntegerField(default=0)
    highway_driving_time = models.BigIntegerField(default=0)
    idling_time = models.BigIntegerField(default=0)
    average_speed = models.FloatField(default=0)
    outside_temp_start = models.FloatField(default=0)
    outside_temp_end = models.FloatField(default=0)
    trip_time = models.BigIntegerField(default=0)
    # energy
    regen = models.BigIntegerField(default=0)
    aircon_consumption = models.BigIntegerField(default=0)
    auxiliary_consumption = models.BigIntegerField(default=0)
    motor_consumption = models.BigIntegerField(default=0)
    idle_consumption = models.BigIntegerField(default=0)
    eco_tree_count = models.BigIntegerField(default=0)
    # accelerator work
    sudden_start_consumption = models.BigIntegerField(default=0)
    sudden_start_time = models.BigIntegerField(default=0)
    sudden_acceleration_consumption = models.BigIntegerField(default=0)
    sudden_acceleration_time = models.BigIntegerField(default=0)
    non_eco_deceleration_consumption = models.BigIntegerField(default=0)
    non_eco_deceleration_time = models.BigIntegerField(default=0)
    # records
    sudden_starts_list = models.JSONField(default=list)
    sudden_accelerations_list = models.JSONField(default=list)
    non_eco_decelerations_list = models.JSONField(default=list)
    non_constant_speeds = models.JSONField(default=list)
    # battery info
    batt_temp_start = models.FloatField(default=0)
    batt_temp_end = models.FloatField(default=0)
    soh_start = models.BigIntegerField(default=0)
    soh_end = models.BigIntegerField(default=0)
    wh_energy_start = models.FloatField(default=0)
    wh_energy_end = models.FloatField(default=0)
    # battery degradation analysis 1
    bda_energy_content_start = models.FloatField(default=0)
    bda_energy_content_end = models.FloatField(default=0)
    bda_avg_temp_start = models.FloatField(default=0)
    bda_max_temp_start = models.FloatField(default=0)
    bda_min_temp_start = models.FloatField(default=0)
    bda_avg_temp_end = models.FloatField(default=0)
    bda_max_temp_end = models.FloatField(default=0)
    bda_min_temp_end = models.FloatField(default=0)
    bda_avg_cell_volt_start = models.FloatField(default=0)
    bda_max_cell_volt_start = models.FloatField(default=0)
    bda_min_cell_volt_start = models.FloatField(default=0)
    bda_regen_end = models.FloatField(default=0)
    bda_number_qc_charges = models.BigIntegerField(default=0)
    bda_number_ac_charges = models.BigIntegerField(default=0)
    bda_soc_end = models.BigIntegerField(default=0)
    bda_resistance_end = models.BigIntegerField(default=0)
    # battery degradation analysis 2
    bda2_capacity_bars_end = models.BigIntegerField(default=0)
    bda2_soc_end = models.BigIntegerField(default=0)
    # other
    headlight_on_time = models.BigIntegerField(default=0)
    average_acceleration = models.FloatField(default=0)
    start_odometer = models.BigIntegerField(default=0)
    max_speed = models.FloatField(default=0)
    used_preheating = models.BooleanField(default=False)


## Probe DOT

class DOTFile(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    capture_ts = models.DateTimeField(null=True, default=None, blank=True)
    upload_ts = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to="probe/dotfiles/%Y/%m/%d/")