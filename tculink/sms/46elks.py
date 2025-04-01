import re
import requests
from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _


class Provider46elks(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('apikey_user', _("API Username")),
        ('apikey_password', _("API Password")),
        ('msn', _("TCU Phone Number (international format)")),
    ]
    HELP_TEXT = _("API credentials are available in your 46elks dashboard.")

    def send(self, message, configuration):
        if "msn" not in configuration or "apikey_user" not in configuration or "apikey_password" not in configuration:
            raise Exception("Configuration is incomplete")

        msn = re.sub('\D', '', configuration['msn'])

        request = requests.post('https://api.46elks.com/a1/sms',
                auth=(configuration['apikey_user'], configuration['apikey_password']), timeout=10,
                data={
                    'from': 'CarWings',
                    'to': f'+{msn}',
                    'message': message
                }, headers={"User-Agent": "OpenCarWings/1.0"}

        )

        return request.status_code == 200