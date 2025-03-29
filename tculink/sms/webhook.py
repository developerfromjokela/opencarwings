import requests
from tculink.sms import BaseSMSProvider


class ProviderWebhook(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('url', "Webhook URL"),
    ]
    HELP_TEXT = "POST-request will be sent to specified webhook URL when necessary."

    def send(self, message, configuration):
        if "url" not in configuration:
            raise Exception("Configuration is incomplete")

        request = requests.post(configuration['url'], json={'message': message},
                                headers={"User-Agent": "OpenCarWings/1.0", "Content-Type": "application/json"})
        return request.status_code == 200