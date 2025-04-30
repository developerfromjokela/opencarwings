import asyncio
from uuid import uuid4

from aioapns import NotificationRequest, PushType
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from api.models import TokenMetadata


@sync_to_async
def get_evinfo(car):
    return car.ev_info

@sync_to_async
def get_location(car):
    return car.location

@sync_to_async
def get_car_owner_info(car):
    return car.owner

@sync_to_async
def get_push_tokens(user):
    tokens = TokenMetadata.objects.filter(user=user)
    apns_tokens = []
    for token in tokens:
        if (token.device_type == 'apple' and len(token.push_notification_key) > 20
                and token.push_notification_key not in apns_tokens):
            apns_tokens.append(token.push_notification_key)
    return {
        "apns": apns_tokens
    }

async def send_vehicle_alert_notification(car, alert_message, subject, apns_client):
    car_owner = await get_car_owner_info(car)
    ev_info = await get_evinfo(car)
    location = await get_location(car)

    await send_email_for_user(car, car_owner, ev_info, location, alert_message, subject)
    await send_push_notification_for_user(car, car_owner, alert_message, subject, apns_client)

async def send_email_for_user(car, car_owner, ev_info, location, alert_message, subject):
    if not car_owner.email_notifications:
        return

    text_content = render_to_string(
        "emails/vehicle_alert.txt",
        context={
            "alert": alert_message,
            "vehicle": car.nickname,
            "range_acon": ev_info.range_acon,
            "range_acoff": ev_info.range_acoff,
            "soc": ev_info.soc,
            "pluggedin": "yes" if ev_info.plugged_in else "no",
            "athome": "yes" if location.home else "no"
        },
    )

    send_mail(
        f"{subject} - OpenCARWINGS",
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [car_owner.email],
        fail_silently=True
    )


"""
Send Push notification messages via Apple APNS and other possible channels
"""
async def send_push_notification_for_user(car, car_owner, message, subject, apns_client):
    tokens = await get_push_tokens(car_owner)

    if apns_client is not None:

        for apns_token in tokens["apns"]:
            try:
                request = NotificationRequest(
                    device_token=apns_token,
                    message={
                        "aps": {
                            "alert": {
                                "title": f"{car.nickname}: {subject}",
                                "subtitle": subject,
                                "body": message,
                            }
                        }
                    },
                    notification_id=str(uuid4()),  # optional
                    time_to_live=3,  # optional
                    push_type=PushType.ALERT,  # optional
                )
                loop = asyncio.get_event_loop()
                print(loop.run_until_complete(apns_client.send_notification(request)))
            except Exception as e:
                print("Failed to send APNS notification:", e)
