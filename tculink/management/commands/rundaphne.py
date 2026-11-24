from daphne.management.commands.runserver import Command as DaphneRunserverCommand
# Run daphne server, don't touch django's runserver

class Command(DaphneRunserverCommand):
    pass