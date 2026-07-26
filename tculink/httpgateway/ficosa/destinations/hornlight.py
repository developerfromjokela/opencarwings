import logging

from asgiref.sync import sync_to_async

from db.models import Car, AlertHistory
from tculink.gdc_proto.ficosa.utils import command_to_destination_id
import tculink.gdc_proto.ficosa.acp as acp
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _

logger = logging.getLogger("ficosa")


def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process horn & light (find car) results
    """

    dest_id = command_to_destination_id(car.command_type)
    if (not dest_id
            or dest_id != destination_id
            or not car.command_requested):
        logger.debug(f"Destination {destination_id} not authorized, details: {dest_id}, sid {source_id}, {car.command_id}, {car.command_requested}")
        # Acknowledge the command, but do not execute.
        # If ACK is not sent, the request will be repeated
        return b'ACK'

    security_hdr, offset = acp.parser.decode_ficosa_vehicle_security_header(bin_data, 0)

    logger.debug("Security HDR: %s", security_hdr)
    __, ts = acp.parser.decode_timestamp(bin_data, offset)
    offset += ts
    security_data, __ = acp.parser.decode_ficosa_vehicle_security_data(bin_data, offset)

    logger.debug("Security DATA: %s", security_data)

    result_code = security_data["code"]
    data_type = security_data["type"]


    if result_code == 1 and data_type == 1:
        logger.debug("Function disabled")
        new_alert = AlertHistory()
        new_alert.type = 94
        new_alert.additional_data = _("{name} function is disabled in TCU").format(name=car.get_command_type_display())
        new_alert.car = car
        new_alert.command_id = source_id
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                new_alert.additional_data,
                _("Could not execute {name}").format(name=car.get_command_type_display())
            )
        , thread_sensitive=False)
    elif data_type == 0x13:
        logger.debug("Failure, code: %d", result_code)
        new_alert = AlertHistory()
        new_alert.type = 94
        message = _("Could not execute {name}, please try again later").format(name=car.get_command_type_display())
        if result_code == 0x82 or result_code == 0x83:
            logger.debug("Conditions not met for command execution")
            message = _("Vehicle conditions not met for command execution.")

        new_alert.additional_data = message
        new_alert.car = car
        new_alert.command_id = source_id
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                message,
                _("Could not execute {name}").format(name=car.get_command_type_display())
            )
        , thread_sensitive=False)
    elif data_type == 0xc:
        logger.debug("CAN Failure, code: %d", result_code)
        new_alert = AlertHistory()
        new_alert.type = 94
        new_alert.additional_data = _("CANBUS failure when executing lock/unlock")
        new_alert.car = car
        new_alert.command_id = source_id
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                _("CANBUS failure when executing {name}").format(name=car.get_command_type_display()),
                _("Could not execute {name}").format(name=car.get_command_type_display())
            )
            , thread_sensitive=False)
    elif data_type == 0:
        logger.debug("Success, code: %d", result_code)
        new_alert = AlertHistory()
        new_alert.type = 15 if result_code == 3 else 14
        new_alert.car = car
        new_alert.command_id = source_id
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                _("Horn & Light started successfully!") if result_code == 3 else _("Horn & Light stopped successfully!"),
                _("Horn & Light")
            )
            , thread_sensitive=False)


    car.command_requested = False
    car.command_result = 0
    car.save()

    return b'ACK'

