from random import randint

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from db.models import Car, COMMAND_TYPES
from tculink.coordinators import InvalidCommandError, SMSError, CommandArgumentError
from tculink.coordinators.stub import TCULink
from tculink.gdc_proto.acp245 import composer
from tculink.gdc_proto.ficosa import smshmac
from tculink.gdc_proto.ficosa.utils import command_to_destination_id, get_config_map_translated
from tculink.sms import send_using_provider, SMSType
from django.utils.translation import gettext_lazy as _

from ui.serializers import FicosaConfigSerializer


def validate_config_cmd(payload):
    payload_serializer = FicosaConfigSerializer(data=payload)
    payload_serializer.is_valid(raise_exception=True)
    config_map = get_config_map_translated()

    config_type = payload_serializer.validated_data["config_type"]
    if config_type not in config_map:
        raise CommandArgumentError("Config type invalid")

    fields = config_map[config_type]["fields"]
    destination_id = config_map[config_type]["destination"]

    if payload_serializer.validated_data["type"] == "send":
        field_data = payload_serializer.validated_data["data"]
        new_config = {}

        for field_key, field_info in fields.items():
            field_type = field_info["type"]
            if field_key not in field_data and field_type != 4:
                raise CommandArgumentError(f"Missing configuration field ${field_key}")
            if field_type == 4:
                if field_key in field_data:
                    if field_data[field_key] < 1:
                        raise CommandArgumentError(f"Service provisioning field ${field_key} cannot be 0")
                    new_config[field_key] = field_data[field_key]
            else:
                value = field_data[field_key]

                if field_type == 0:
                    if field_info.get("max") and value > field_info["max"]:
                        raise CommandArgumentError(f"{field_info['label']} is more than {field_info['max']}")
                    if field_info.get("min") and value < field_info["min"]:
                        raise CommandArgumentError(f"{field_info['label']} is less than {field_info['min']}")
                    new_config[field_key] = int(value)

                elif field_type == 1:
                    new_config[field_key] = value == True

                elif field_type in (2, 3):
                    if field_info.get("max") and len(value) > field_info["max"]:
                        raise CommandArgumentError(f"{field_info['label']} is more than {field_info['max']} characters")
                    if field_info.get("min") and len(value) < field_info["min"]:
                        raise CommandArgumentError(f"{field_info['label']} is less than {field_info['min']} characters")

                    if field_type == 2:
                        if not value.isascii():
                            raise CommandArgumentError(f"{field_info['label']} must contain only ASCII characters")

                new_config[field_key] = value

        if not new_config:
            raise CommandArgumentError("No configuration fields to send!")
        return {"type": "send", "data": new_config, "config_type": config_type}, destination_id

    if payload_serializer.validated_data["type"] == "current":
        config_type = payload_serializer.validated_data["config_type"]
        if config_type not in config_map:
            raise CommandArgumentError("Config type invalid")
        if not config_map[config_type]["query_support"]:
            raise CommandArgumentError("Config type does not support querying current configuration")
        return {"type": "current", "config_type": config_type}, destination_id

    raise CommandArgumentError(f"Invalid type!")


class Ficosa2016(TCULink):
    CODE = 'ficosa2016'
    SUPPORTED_COMMANDS = [1,2,3,4,6,7,8,9,10,11,12,13,14,15]
    REQUIRED_SMS_TYPES = [SMSType.BINARY]

    def send_command(self, command: int, payload, car: Car):
        if command in dict(COMMAND_TYPES) and command in self.SUPPORTED_COMMANDS:
            # check if command needs payload
            if payload is not None and command not in [3,15]:
                raise CommandArgumentError("Command does not support payload field")
            if command == 15:
                try:
                    payload, destination_id = validate_config_cmd(payload)
                except ValidationError as e:
                    raise CommandArgumentError(str(e))
            else:
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
            car.command_payload = payload
            car.command_request_time = timezone.now()
            car.save()
            return car
        else:
            raise InvalidCommandError()