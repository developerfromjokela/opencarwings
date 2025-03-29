from django.conf import settings


def send_using_provider(message, configuration):
    parts = settings.SMS_PROVIDERS[configuration.get('provider', '')][1].split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)

    provider = m()
    return provider.send(message, configuration)

class BaseSMSProvider:
    CONFIGURATION_FIELDS = []
    HELP_TEXT = None

    def send(self, message, configuration):
        raise NotImplementedError()