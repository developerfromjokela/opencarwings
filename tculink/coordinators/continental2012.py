from random import randint

from django.utils import timezone

from db.models import Car, COMMAND_TYPES
from tculink.coordinators import InvalidCommandError, SMSError, CommandArgumentError
from tculink.coordinators.stub import TCULink
from tculink.sms import send_using_provider, SMSType
from django.conf import settings
from django.utils.translation import gettext_lazy as _

def convert_abrp(car: Car):
    power = 0
    if car.ev_info.power_available:
        if car.ev_info.charging and car.ev_info.limit_chg_time != 2047:
            power = -1.2
        if car.ev_info.charging and car.ev_info.full_chg_time != 2047:
            power = -3.6
        if car.ev_info.charging and car.ev_info.obc_6kw != 4095 and car.ev_info.obc_6kw != 2047:
            power = -6.6
        if car.ev_info.quick_charging:
            power = -35  # this is just the most realistic chademo speed :)

    return {
        "power": power,
        "speed": 0,
        "soc": car.ev_info.soc_display if car.ev_info.soc_display > 0 else car.ev_info.soc,
        "is_charging": car.ev_info.charging,
        "is_dcfc": car.ev_info.quick_charging,
        "is_parked": car.ev_info.car_gear == 0,
        "capacity": ((car.ev_info.max_gids * (car.ev_info.soh / 100)) * 80) / 1000,
        "soe": str(car.ev_info.gids * 80),
        "soh": car.ev_info.soh,
        "est_battery_range": car.ev_info.range_acon
    }

class Continental2012(TCULink):
    CODE = 'continental2012'
    SUPPORTED_COMMANDS = [1,2,3,4,5]
    REQUIRED_SMS_TYPES = [SMSType.TEXT]


    def send_command(self, command: int, payload, car: Car):
        if command in dict(COMMAND_TYPES) and command in self.SUPPORTED_COMMANDS:
            if payload is not None and set(payload.keys()) != {"timer"}:
                raise CommandArgumentError("Command does not support payload field")
            try:
                sms_result = send_using_provider(settings.ACTIVATION_SMS_MESSAGE, car.sms_config, car.tcu_model)
                if not sms_result:
                    raise SMSError(_('Failed to send SMS message to TCU. Please try again in a moment.'))
            except Exception as e:
                raise SMSError(str(e))
            car.command_type = command
            car.command_id = randint(10000, 99999)
            car.command_requested = True
            car.command_result = -1
            car.command_payload = payload
            car.command_request_time = timezone.now()
            car.save(update_fields=["command_type", "command_id", "command_requested",
                                    "command_result", "command_payload", "command_request_time"])
            return car
        else:
            raise InvalidCommandError()