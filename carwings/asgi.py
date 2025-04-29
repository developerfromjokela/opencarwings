"""
ASGI config for carwings project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carwings.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import ProtocolTypeRouter, URLRouter
channel_layer = get_channel_layer()

from django.core.asgi import get_asgi_application
from django.utils.translation.trans_real import parse_accept_lang_header, language_code_re, \
    get_supported_language_variant
from django.utils import translation


@database_sync_to_async
def get_user(headers):
    from rest_framework.authtoken.models import Token
    try:
        token_name, token_key = headers[b'authorization'].decode().split()
        if token_name == 'Token':
            token = Token.objects.get(key=token_key)
            return token.user
    except Token.DoesNotExist:
        from django.contrib.auth.models import AnonymousUser
        return AnonymousUser()


class TokenAuthMiddleware:

    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope, receive, send):
        return TokenAuthMiddlewareInstance(scope, self).__call__(receive, send)


class TokenAuthMiddlewareInstance:
    def __init__(self, scope, middleware):
        self.middleware = middleware
        self.scope = dict(scope)
        self.inner = self.middleware.inner

    async def __call__(self, receive, send):
        headers = dict(self.scope['headers'])
        if b'accept-language' in headers:
            lang_hdr = headers[b'accept-language'].decode()
            activated_lang = None
            for accept_lang, unused in parse_accept_lang_header(lang_hdr):
                if accept_lang == "*":
                    break

                if not language_code_re.search(accept_lang):
                    continue

                try:
                    activated_lang = get_supported_language_variant(accept_lang)
                    break
                except LookupError:
                    continue

            if activated_lang is not None:
                self.scope['lang'] = activated_lang
                translation.activate(activated_lang)

        if b'authorization' in headers:
            self.scope['user'] = await get_user(headers)
        return await self.inner(self.scope, receive, send)

TokenAuthMiddlewareStack = lambda inner: TokenAuthMiddleware(AuthMiddlewareStack(inner))
from api.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": TokenAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)

