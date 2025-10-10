from django import template
from django.utils.translation import gettext_lazy as _

from tculink.carwings_proto.probe_config import PROBE_CONFIG_INFO

register = template.Library()

@register.filter
def probe_config_name(value):
    if value == -1:
        return "--"
    name = PROBE_CONFIG_INFO.get(value, _("Unknown"))
    return f"{name} ({value})"