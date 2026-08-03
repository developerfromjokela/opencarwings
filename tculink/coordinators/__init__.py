class TCUCoordinatorError(Exception):
    pass

class InvalidCommandError(TCUCoordinatorError):
    pass

class CommandArgumentError(TCUCoordinatorError):
    pass

class UnsupportedCommandError(TCUCoordinatorError):
    pass

class SMSError(TCUCoordinatorError):
    pass


def get_supported_commands(code: str) -> list[int]:
    parts = COORDINATORS.get(code).split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)

    coordinator = m()
    return coordinator.SUPPORTED_COMMANDS

def get_required_sms_types(code: str):
    parts = COORDINATORS.get(code).split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)

    coordinator = m()
    return coordinator.REQUIRED_SMS_TYPES

COORDINATORS = {
    'continental2012': "tculink.coordinators.continental2012.Continental2012",
    'ficosa2016': "tculink.coordinators.ficosa2016.Ficosa2016",
}