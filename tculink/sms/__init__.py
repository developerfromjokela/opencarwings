from enum import Enum

from django.conf import settings


def send_using_provider(message, configuration, tcu_id):
    parts = settings.SMS_PROVIDERS[configuration.get('provider', '')][1].split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)

    provider = m()
    if not isinstance(message, str):
        if SMSType.BINARY not in provider.SUPPORTED_TYPES:
            raise Exception("SMS provider does not support binary messages!")
    configuration['tcu_id'] = tcu_id
    return provider.send(message, configuration)

class SMSType(Enum):
    TEXT = 0
    BINARY = 1

class BaseSMSProvider:
    CONFIGURATION_FIELDS = []
    HELP_TEXT = None
    SUPPORTED_TYPES = []

    def send(self, message, configuration):
        raise NotImplementedError()