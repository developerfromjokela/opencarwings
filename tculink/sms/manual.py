from tculink.sms import BaseSMSProvider
from django.utils.translation import gettext_lazy as _


class ProviderManual(BaseSMSProvider):
    CONFIGURATION_FIELDS = []
    HELP_TEXT = _("Important: With this option, you will need to manually send the SMS yourself for this to work. No automated messaging will be set up.")

    def send(self, message, configuration):
        return True