import requests

from tculink.gdc_proto.ficosa import pdu
from tculink.sms import BaseSMSProvider, SMSType
from django.utils.translation import gettext_lazy as _


class ProviderWebhook(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('url', _("Webhook URL")),
        ('phone', _("TCU Phone Number (international format)")),
    ]
    HELP_TEXT = _("POST-request will be sent to specified webhook URL when necessary.")
    SUPPORTED_TYPES = [SMSType.TEXT, SMSType.BINARY]

    def send(self, message, configuration):
        if "url" not in configuration:
            raise Exception("Configuration is incomplete")

        pdu_data = None
        pdu_len = 0
        if isinstance(message, str):
            msg_type = SMSType.TEXT.value
        else:
            msg_type = SMSType.BINARY.value
            if "phone" not in configuration:
                raise Exception("Phone number missing, cannot make PDU!")
            pdu_data, pdu_len = pdu.data_pdu(configuration["phone"], message)
            pdu_data = pdu_data.hex()
            message = message.hex()

        request = requests.post(configuration['url'], json={'message': message, "type": msg_type, "pdu": pdu_data, "pdu_length": pdu_len}, timeout=10,
                                headers={"User-Agent": "OpenCarWings/1.0", "Content-Type": "application/json"})
        return request.status_code == 200