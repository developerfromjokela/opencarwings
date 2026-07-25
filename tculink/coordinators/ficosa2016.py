from random import randint

from django.utils import timezone

from db.models import Car, COMMAND_TYPES
from tculink.coordinators import InvalidCommandError, SMSError
from tculink.coordinators.stub import TCULink
from tculink.gdc_proto.acp245 import composer
from tculink.gdc_proto.ficosa import smshmac
from tculink.gdc_proto.ficosa.utils import command_to_destination_id
from tculink.sms import send_using_provider, SMSType
from django.utils.translation import gettext_lazy as _

class Ficosa2016(TCULink):
    CODE = 'ficosa2016'
    SUPPORTED_COMMANDS = [1,2,3,4,6,7,8,9,10,11,12,13,14]
    REQUIRED_SMS_TYPES = [SMSType.BINARY]


    def send_command(self, command: int, car: Car):
        if command in dict(COMMAND_TYPES) and command in self.SUPPORTED_COMMANDS:
            destination_id = command_to_destination_id(command)
            source_id = randint(200, 255)

            acp_msg = bytearray()

            acp_msg += composer.VersionFicosa(sw_version=2, hw_1=1, hw_2=0, hw_3=2).encode()
            acp_msg += composer.VehDesc(vin=car.vin, dcm=car.tcu_model).encode()
            acp_msg += destination_id.to_bytes(1, "little")
            acp_msg += source_id.to_bytes(1, "little")
            acp_msg +=  composer.Timestamp().encode()

            msg = bytearray()
            msg += composer.AppHeader(app_id=2, mcf=3, length=len(acp_msg), special_flag=1).encode()
            msg += acp_msg

            hmac_key = smshmac.HMAC_KEY
            if car.hmac_key and car.hmac_key is not None and len(car.hmac_key) > 0:
                hmac_key = bytes.fromhex(hmac_key)

            msg_hmac = smshmac.sms_acp_rn_hmac(msg, hmac_key)

            try:
                sms_result = send_using_provider(msg_hmac, car.sms_config)
                if not sms_result:
                    raise SMSError(_('Failed to send SMS message to TCU. Please try again in a moment.'))
            except Exception as e:
                raise SMSError(str(e))
            car.command_type = command
            # GDC range is from 0x7f - 0xff
            car.command_id = source_id
            car.command_requested = True
            car.command_result = -1
            car.command_request_time = timezone.now()
            car.save()
            return car
        else:
            raise InvalidCommandError()