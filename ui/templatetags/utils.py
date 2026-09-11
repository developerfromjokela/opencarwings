from django import template

register = template.Library()

@register.filter
def fix_gforce(value):
    if value is not None and value > 65535:
        byte_value = value.to_bytes(3, byteorder="big", signed=False)
        return int.from_bytes(byte_value[1:], byteorder="big", signed=False)
    return value