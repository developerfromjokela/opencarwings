import zoneinfo

from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated and request.user.timezone:
            timezone.activate(zoneinfo.ZoneInfo(request.user.timezone))
        else:
            timezone.deactivate()
        return self.get_response(request)