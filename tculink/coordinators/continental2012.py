from random import randint

from django.utils import timezone

from db.models import Car, COMMAND_TYPES
from tculink.coordinators import InvalidCommandError, SMSError, CommandArgumentError
from tculink.coordinators.stub import TCULink
from tculink.sms import send_using_provider, SMSType
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Continental2012(TCULink):
    CODE = 'continental2012'
    SUPPORTED_COMMANDS = [1,2,3,4,5]
    REQUIRED_SMS_TYPES = [SMSType.TEXT]


    def send_command(self, command: int, payload, car: Car):
        if command in dict(COMMAND_TYPES) and command in self.SUPPORTED_COMMANDS:
            if payload is not None and set(payload.keys()) != {"timer_id"}:
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
            car.save()
            return car
        else:
            raise InvalidCommandError()