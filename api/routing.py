from django.urls import path

from api import consumers

websocket_urlpatterns = [
    path("ws/notif/", consumers.NotificationConsumer.as_asgi()),
    path("ws/smsgateway/", consumers.SMSGatewayConsumer.as_asgi()),
]
