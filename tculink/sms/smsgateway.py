from tculink.gdc_proto.ficosa import pdu
from tculink.sms import BaseSMSProvider, SMSType
from django.utils.translation import gettext_lazy as _
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class ProviderSMSGateway(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('device_id', _("Device ID")),
        ('encryption_key', _("Encryption Key")),
        ('phone', _("TCU Phone Number (international format)"))
    ]

    HELP_TEXT = _("Use your old smartphone or USB modem as a gateway to send SMS. Once app has been installed, write values shown in the app to their respective fields. More information: ")
    LINK = "https://github.com/developerfromjokela/opencarwings-sms"
    SUPPORTED_TYPES = [SMSType.TEXT, SMSType.BINARY]

    def send(self, message, configuration):
        if "device_id" not in configuration or "phone" not in configuration:
            raise Exception("Configuration is incomplete")

        pdu_data = None
        pdu_len = 0
        if isinstance(message, str):
            msg_type = SMSType.TEXT.value
        else:
            msg_type = SMSType.BINARY.value
            pdu_data, pdu_len = pdu.data_pdu(configuration["phone"], message)
            pdu_data = pdu_data.hex()
            message = message.hex()

        channel_layer = get_channel_layer()


        if msg_type == SMSType.TEXT:
            payload = {
                'type': 'relay_sms',
                'sms': message,
                'phone': configuration['phone'],
            }
        else:
            payload = {
                'type': 'relay_pdu',
                'data': message,
                'pdu': pdu_data,
                'length': pdu_len,
                'phone': configuration['phone'],
            }
        async_to_sync(channel_layer.group_send)(f'sms_{configuration["device_id"]}', payload)
        return True