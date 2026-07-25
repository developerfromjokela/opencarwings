import logging

from tculink.coordinators import COORDINATORS
from tculink.sms import SMSType
from db.models import Car


def send_command_using_provider(command: int, car: Car):
    parts = COORDINATORS.get(car.tcu_type).split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)

    coordinator = m()
    return coordinator.send_command(command, car)

# TCU command coordinator for different models
class TCULink:
    CODE: str = ''
    SUPPORTED_COMMANDS: list[int] = []
    REQUIRED_SMS_TYPES: list[SMSType] = []

    def __init__(self):
        pass

    def send_command(self, command: int, car: Car):
        raise NotImplementedError()