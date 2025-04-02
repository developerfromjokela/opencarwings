from django.conf import settings

from tculink.sms import BaseSMSProvider
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _


class ProviderManual(BaseSMSProvider):
    CONFIGURATION_FIELDS = []
    HELP_TEXT = format_lazy(_("Important: With this option, you will need to manually send the SMS yourself for this to work. No automated messaging will be set up. SMS message to send after you've issued a command on the website: {sms}"), sms=settings.ACTIVATION_SMS_MESSAGE)

    def send(self, message, configuration):
        return True