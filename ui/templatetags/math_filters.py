from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0  # Fallback to 0 if conversion fails


@register.filter
def divide(value, arg):
    try:
        if value == 0:
            return 0.0
        return value/arg
    except (ValueError, TypeError):
        return 0.0  # Fallback to 0 if conversion fails

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")
