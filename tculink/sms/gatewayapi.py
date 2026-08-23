import base64
import re
from typing import Any

import requests

from tculink import VERSION
from tculink.sms import BaseSMSProvider, SMSType
from django.utils.translation import gettext_lazy as _

class ProviderGatewayAPI(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('apikey', _("API Key")),
        ('msn', _("TCU Phone Number (international format)")),
    ]
    HELP_TEXT = _("API credentials are available in gatewayapi.com API section.")
    SUPPORTED_TYPES = [SMSType.TEXT, SMSType.BINARY]

    def send(self, message, configuration):
        if "apikey" not in configuration or "msn" not in configuration:
            raise Exception("Configuration is incomplete")

        msn = re.sub('\\D', '', configuration['msn'])

        if len(msn) < 1:
            raise Exception("Phone number is not valid")

        payload: dict[str, Any] = {
            "recipients": [{"msisdn": int(msn)}]
        }

        if isinstance(message, str):
            payload['message'] = message
        else:
            payload['payload'] = base64.b64encode(message).decode()
            payload['encoding'] = "BINARY"

        request = requests.post('https://gatewayapi.com/rest/mtsms',
                timeout=10, json=payload, headers={
                "User-Agent": f"OpenCarWings/{VERSION}",
                "Content-Type": "application/json",
                "Authorization": f"Token {configuration['apikey']}"
            }
        )

        return request.status_code == 200