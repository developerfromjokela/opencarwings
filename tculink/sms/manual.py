from tculink.sms import BaseSMSProvider


class ProviderManual(BaseSMSProvider):
    CONFIGURATION_FIELDS = []
    HELP_TEXT = "Important: With this option, you will need to manually send the SMS yourself for this to work. No automated messaging will be set up."

    def send(self, message, configuration):
        return True