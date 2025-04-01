import requests
from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _


class ProviderWebhook(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('url', _("Webhook URL")),
    ]
    HELP_TEXT = _("POST-request will be sent to specified webhook URL when necessary.")

    def send(self, message, configuration):
        if "url" not in configuration:
            raise Exception("Configuration is incomplete")

        request = requests.post(configuration['url'], json={'message': message}, timeout=10,
                                headers={"User-Agent": "OpenCarWings/1.0", "Content-Type": "application/json"})
        return request.status_code == 200