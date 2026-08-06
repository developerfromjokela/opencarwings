import re
from typing import Any

import requests

from tculink import VERSION
from tculink.sms import BaseSMSProvider, SMSType
from django.utils.translation import gettext_lazy as _

class ProviderSevenIO(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('apikey', _("API Key")),
        ('msn', _("TCU Phone Number (international format)")),
    ]
    HELP_TEXT = _("API credentials are available in dashboard.seven.io Developer section. Remember to add 'OCW' as Sender ID under account settings!")
    SUPPORTED_TYPES = [SMSType.TEXT, SMSType.BINARY]

    def send(self, message, configuration):
        if "apikey" not in configuration or "msn" not in configuration:
            raise Exception("Configuration is incomplete")

        msn = re.sub('\D', '', configuration['msn'])

        if len(msn) < 1:
            raise Exception("Phone number is not valid")

        payload: dict[str, Any] = {
            # without sender, sms doesn't get delivered
            "from": "OCW",
            "to": msn,
        }

        if isinstance(message, str):
            payload['text'] = message
        else:
            payload['is_binary'] = 1
            payload['text'] = message.hex()

        request = requests.post('https://gateway.seven.io/api/sms',
                timeout=10, data=payload, headers={
                "User-Agent": f"OpenCarWings/{VERSION}",
                "Accept": "application/json",
                "X-Api-Key": configuration['apikey']
            }
        )

        return request.status_code == 200 and request.json().get('status', '') == '100'