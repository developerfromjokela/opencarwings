import logging

from asgiref.sync import sync_to_async

from db.models import Car, AlertHistory
import tculink.gdc_proto.ficosa.acp as acp
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _

logger = logging.getLogger("ficosa")


def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process vehicle theft alarm
    """
    logger.info("Received new theft alarm!")
    security_hdr, offset = acp.parser.decode_ficosa_vehicle_security_header(bin_data, 0)

    logger.debug("Security HDR: %s", security_hdr)
    __, ts = acp.parser.decode_timestamp(bin_data, offset)
    offset += ts
    security_data, __ = acp.parser.decode_ficosa_vehicle_security_data(bin_data, offset)

    logger.debug("Security DATA: %s", security_data)

    new_alert = AlertHistory()
    new_alert.type = 20
    new_alert.car = car
    new_alert.command_id = source_id
    new_alert.save()
    sync_to_async(
        send_vehicle_alert_notification(
            car,
            _("Burglar alarm has been triggered"),
            _("Burglar Alarm")
        )
        , thread_sensitive=False)

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
