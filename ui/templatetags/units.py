from django import template

from ui.utils import convert_tpms_pressure, convert_tpms_pressure_bar

register = template.Library()


@register.simple_tag(takes_context=True)
def local_dist(context, value, *args, decimals=2):
    try:
        # Convert value to float to handle numeric inputs
        value = float(value)

        # Ensure decimals is a valid integer and within reasonable bounds
        decimals = int(decimals)
        if decimals < 0:
            decimals = 0

        # Access request from template context
        request = context.get('request') if context else None

        # Check if request exists and user prefers imperial units
        if request and hasattr(request, 'user') and hasattr(request.user,
                                                            'units_imperial') and request.user.units_imperial:
            # Convert km to miles (1 km = 0.621371 miles)
            value = value * 0.621371
            return f"{value:.{decimals}f} mi"
        return f"{value:.{decimals}f} km"
    except (ValueError, TypeError, AttributeError):
        return value  # Return original value if conversion fails or request is unavailable

@register.simple_tag(takes_context=True)
def local_spd(context, value, *args, decimals=2):
    try:
        # Convert value to float to handle numeric inputs
        value = float(value)

        # Ensure decimals is a valid integer and within reasonable bounds
        decimals = int(decimals)
        if decimals < 0:
            decimals = 0

        # Access request from template context
        request = context.get('request') if context else None

        # Check if request exists and user prefers imperial units
        if request and hasattr(request, 'user') and hasattr(request.user,
                                                            'units_imperial') and request.user.units_imperial:
            # Convert km to miles (1 km = 0.621371 miles)
            value = value * 0.621371
            return f"{value:.{decimals}f} mph"
        return f"{value:.{decimals}f} km/h"
    except (ValueError, TypeError, AttributeError):
        return value  # Return original value if conversion fails or request is unavailable

@register.simple_tag(takes_context=True)
def local_cons(context, value, *args, decimals=2):
    try:
        # Convert value to float to handle numeric inputs
        value = float(value)

        # Ensure decimals is a valid integer and within reasonable bounds
        decimals = int(decimals)
        if decimals < 0:
            decimals = 0

        # Access request from template context
        request = context.get('request') if context else None

        # Check if request exists and user prefers imperial units
        if request and hasattr(request, 'user') and hasattr(request.user,
                                                            'units_imperial') and request.user.units_imperial:
            # Convert km to miles (1 km = 0.621371 miles)
            value = value * 1.609344
            return f"{value:.{decimals}f} Wh/mi"
        return f"{value:.{decimals}f} Wh/km"
    except (ValueError, TypeError, AttributeError):
        return value  # Return original value if conversion fails or request is unavailable

@register.simple_tag(takes_context=True)
def local_tpms(context, value, *args, decimals=2, unit_label=True):
    try:
        # Ensure decimals is a valid integer and within reasonable bounds
        decimals = int(decimals)
        if decimals < 0:
            decimals = 0

        # Access request from template context
        request = context.get('request') if context else None

        # Check if request exists and user prefers imperial units
        if request and hasattr(request, 'user') and hasattr(request.user,
                                                            'units_imperial') and request.user.units_imperial:
            value = convert_tpms_pressure(value)
            unit = " PSI"
            if not unit_label:
                unit = ""
            return f"{value:.{decimals}f}{unit}"
        value = convert_tpms_pressure_bar(value)
        unit = " Bar"
        if not unit_label:
            unit = ""
        return f"{value:.{decimals}f}{unit}"
    except (ValueError, TypeError, AttributeError):
        return value  # Return original value if conversion fails or request is unavailable

@register.simple_tag(takes_context=True)
def local_tpms_unit(context, *args):
    try:
        request = context.get('request') if context else None
        if request and hasattr(request, 'user') and hasattr(request.user,
                                                            'units_imperial') and request.user.units_imperial:
            return "PSI"
        return "Bar"
    except (ValueError, TypeError, AttributeError):
        return ""