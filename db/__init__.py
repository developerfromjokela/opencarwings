from django.apps import AppConfig


class DbAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'db'

    def ready(self):
        import db.signals

class CommandPinError(Exception):
    pass