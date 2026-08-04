import logging

from asgiref.sync import sync_to_async

from db.models import Car, AlertHistory
import tculink.gdc_proto.ficosa.acp as acp
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _

logger = logging.getLogger("ficosa")


def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process vehicle health data
    """

    logger.info(_("Received new health report!"))
    logger.info("VehHealth %s", bin_data.hex())
    logger.info("VehHealth acp %s", acp_data)
    new_alert = AlertHistory()
    new_alert.type = 19
    new_alert.additional_data = _("Vehicle Health Report")
    new_alert.car = car
    new_alert.command_id = source_id
    new_alert.save()
    sync_to_async(
        send_vehicle_alert_notification(
            car,
            _("Received new health report!"),
            _("Vehicle Health Report")
        )
        , thread_sensitive=False)

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
