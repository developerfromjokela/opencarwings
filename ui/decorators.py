import time
from functools import wraps

from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import gettext as _
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

OTP_FRESHNESS = 5 * 60  # 5 minutes


def block_apikey_api(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request, 'auth') and isinstance(request.auth, Token):
            return Response({'status': False, 'cause': 'Cannot perform this action with API token!'}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped_view

def block_apikey(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Token '):
            return Response({'status': False, 'cause': 'Cannot perform this action with API token!'}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped_view

def require_recent_2fa(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_2fa_enabled():
            return view_func(request, *args, **kwargs)

        last_2fa = request.session.get('last_2fa')
        is_recent = last_2fa is not None and (time.time() - last_2fa) < OTP_FRESHNESS

        if is_recent:
            return view_func(request, *args, **kwargs)

        if request.method == 'POST' and request.POST.get('reverify_2fa') == '1':
            otp_code = request.POST.get('otp')
            if otp_code and request.user.verify_otp(otp_code):
                request.session['last_2fa'] = time.time()
                return view_func(request, *args, **kwargs)
            messages.error(request, _("Code is not valid!"))

        return render(request, 'ui/reverify_otp.html', {
            'reverify_2fa': True,
            'next_path': request.get_full_path(),
        })

    return _wrapped_view