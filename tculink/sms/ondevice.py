from django.conf import settings

from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _


class ProviderOnDevice(BaseSMSProvider):
    CONFIGURATION_FIELDS = [
        ('phone', _("International Phone number of TCU (+xxxxxxxxxxxx)")),
    ]

    HELP_TEXT = _("With this option, the website will redirect you to send the SMS on your phone. Or with the mobile app, it will send it automatically if possible. This method won't work via API or automations, only from the website or mobile app!")

    def send(self, message, configuration):
        return True