import logging

import tculink.gdc_proto.ficosa.acp as acp
from db.models import Car
from tculink.gdc_proto.ficosa.utils import CONFIGURATION_MAP

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

    config_results, _ = acp.parser.decode_acp_config_results(bin_data)

    logger.debug(f"ConfigResults: {config_results}")
    logger.debug(f"LeftoverData: {bin_data.hex()}")

    car.command_requested = False
    car.command_result = 0
    car.save()

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
