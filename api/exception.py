from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, ValidationError):
        errors_list = []
        data = response.data

        def extract_messages(detail):
            if isinstance(detail, dict):
                for value in detail.values():
                    extract_messages(value)
            elif isinstance(detail, list):
                for item in detail:
                    extract_messages(item)
            else:
                errors_list.append(str(detail))

        extract_messages(data)

        combined_error = ", ".join(errors_list)

        response.data = {
            "status": False,
            "error": combined_error
        }

    return response