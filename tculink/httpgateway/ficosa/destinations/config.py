import logging

from asgiref.sync import sync_to_async

import tculink.gdc_proto.ficosa.acp as acp
from db.models import Car, AlertHistory
from tculink.gdc_proto.ficosa.utils import CONFIGURATION_MAP
from tculink.utils.notifications import send_vehicle_alert_notification

logger = logging.getLogger("ficosa")


def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process configuration results
    """

    dest_id = None
    if car.command_type == 15 and car.command_payload is not None:
        dest_id = CONFIGURATION_MAP[car.command_payload["config_type"]]["destination"]

    if (not dest_id
            or dest_id != destination_id
            or not car.command_requested):
        logger.debug(f"Destination {destination_id} not authorized, details: {dest_id}, sid {source_id}, {car.command_id}, {car.command_requested}")
        # Acknowledge the command, but do not execute.
        # If ACK is not sent, the request will be repeated
        return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 0)

    config_template = CONFIGURATION_MAP[car.command_payload["config_type"]]
    config_results, _ = acp.parser.decode_acp_config_results(bin_data)

    logger.debug(f"ConfigResults: {config_results}")
    logger.debug(f"ConfigData: {bin_data.hex()}")

    triplet = (0, 0, 0)

    for itm in config_results["triples"]:
        if itm[0] == config_template["service_type"]:
            triplet = itm
            break

    if triplet[0] == 0 or triplet[2] != 1:
        car.command_result = 1
        new_alert = AlertHistory()
        new_alert.type = 92
        new_alert.car = car
        new_alert.command_id = car.command_id
        new_alert.additional_data = _(config_template["label"])
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                _(config_template["label"]),
                _("Configuration Update Failed"),
            )
        , thread_sensitive=False)
    else:
        # success
        new_alert = AlertHistory()
        new_alert.type = 18
        new_alert.car = car
        new_alert.command_id = car.command_id
        new_alert.additional_data = _(config_template["label"])
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                _(config_template["label"]),
                _("Configuration Updated Successfully"),
            )
        , thread_sensitive=False)


    car.command_requested = False
    car.save()

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
