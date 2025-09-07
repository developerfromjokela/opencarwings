from django import template

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