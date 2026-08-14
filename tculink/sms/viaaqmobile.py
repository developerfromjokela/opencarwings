import requests
from django.conf import settings

from tculink import VERSION
from tculink.coordinators import SMSError
from tculink.sms import BaseSMSProvider, SMSType
from django.utils.translation import gettext_lazy as _

"""
For larger hosted instances
"""
class ProviderViaaqMobileGlobal(BaseSMSProvider):
    CONFIGURATION_FIELDS = []
    HELP_TEXT = _("Your subscription is automatically linked with OpenCARWINGS, using TCU ID shown in mobile.viaaq.eu/dashboard")
    SUPPORTED_TYPES = [SMSType.TEXT, SMSType.BINARY]

    def _send_req(self, message, configuration, apikey):
        if isinstance(message, str):
            msg_type = SMSType.TEXT.value
        else:
            msg_type = SMSType.BINARY.value
            message = message.hex()

        request = requests.post("https://mobile.viaaq.eu/api/v1/sms", json={
            "tcu_id": configuration['tcu_id'],
            "data": message,
            "type": "binary" if msg_type == 1 else "text"
        }, timeout=10, headers={"User-Agent": f"OpenCarWings/{VERSION}",
                                "Content-Type": "application/json",
                                "X-Api-Token": apikey})
        if request.status_code == 400:
            raise SMSError(_("Could not find mobile subscription in viaaq mobile. Are you sure it's active?"))
        if request.status_code == 403:
            raise SMSError(_("You do not have permission to send SMS messages to this subscription"))
        if request.status_code == 401:
            raise SMSError(_("Invalid API Key"))
        return request.status_code == 200

    def send(self, message, configuration):
        return self._send_req(message, configuration, settings.VIAAQMOBILE_KEY)

"""
For self-hosting
"""
class ProviderViaaqMobileAPIToken(ProviderViaaqMobileGlobal):
    CONFIGURATION_FIELDS = [
        ('apikey', _("API Key"))
    ]

    def send(self, message, configuration):
        if "apikey" not in configuration:
            raise Exception("Configuration is incomplete")

        return self._send_req(message, configuration, configuration['apikey'])