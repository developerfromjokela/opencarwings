from django import template

register = template.Library()

@register.filter
def fix_gforce(value):
    if value is not None and value > 65535:
        byte_value = int(value).to_bytes(3, byteorder="big", signed=False)
        return (int.from_bytes(byte_value[1:], byteorder="big", signed=False)) / 9.80665
    elif value is not None and value > 0:
        return int(value) / 9.80665
    return 0