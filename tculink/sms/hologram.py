import requests
from tculink.sms import BaseSMSProvider


class ProviderHologram(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('apikey', "API Key"),
        ('device_id', "Device ID"),
    ]
    HELP_TEXT = "API credentials are available in Hologram dashboard Settings."

    def send(self, message, configuration):
        if "apikey" not in configuration or "device_id" not in configuration:
            raise Exception("Configuration is incomplete")


        request = requests.post('https://dashboard.hologram.io/api/1/sms/incoming',
                auth=('apikey', configuration['apikey']),
                json={
                    'deviceid': configuration['device_id'],
                    'body': message
                }, headers={"User-Agent": "OpenCarWings/1.0", "Content-Type": "application/json"}
        )

        return request.status_code == 200