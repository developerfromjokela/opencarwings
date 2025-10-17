from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class ProviderSMSGateway(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('device_id', _("Device ID")),
        ('encryption_key', _("Encryption Key")),
        ('phone', _("TCU Phone Number (international format)"))
    ]

    HELP_TEXT = _("Use your old smartphone as a gateway to send SMS. Once app has been installed, write values shown in the app to their respective fields. More information: ")
    LINK = "https://github.com/developerfromjokela/opencarwings-sms"

    def send(self, message, configuration):
        if "device_id" not in configuration or "phone" not in configuration:
            raise Exception("Configuration is incomplete")

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sms_{configuration["device_id"]}',
            {
                'type': 'relay_sms',
                'sms': message,
                'phone': configuration['phone'],
            }
        )
        return True