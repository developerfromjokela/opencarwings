import logging

from asgiref.sync import sync_to_async

import tculink.gdc_proto.ficosa.acp as acp
from db.models import Car, AlertHistory
from tculink.gdc_proto.ficosa.utils import CONFIGURATION_MAP
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _

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

    try:
        config_template = CONFIGURATION_MAP[car.command_payload["config_type"]]
        config_results, __ = acp.parser.decode_acp_config_results(bin_data)

        logger.debug(f"ConfigResults: {config_results}")
        logger.debug(f"ConfigData: {bin_data.hex()}")

        if destination_id == 0xf5:
            tcu_config = car.tcu_configuration
            curr_ficosa_conf = tcu_config.ficosa_config.get("svc_provision", {})

            failed_configs = []
            svc_map = {}
            for key, detail in config_template["fields"].items():
                detail["key"] = key
                svc_map[detail["info_id"]] = detail

            for itm in config_results["triples"]:
                svc_id = itm[0]
                svc_status = itm[1]
                save_result = itm[2]

                if svc_id in svc_map:
                    svc_info = svc_map[svc_id]
                    curr_ficosa_conf[svc_info["key"]] = svc_status

                    if save_result < 1:
                        failed_configs.append(svc_info["label"])

            if len(failed_configs) > 0:
                car.command_result = 1
                new_alert = AlertHistory()
                new_alert.type = 92
                new_alert.car = car
                new_alert.command_id = car.command_id
                new_alert.additional_data = ", ".join([_(label) for label in failed_configs])
                new_alert.save()
                sync_to_async(
                    send_vehicle_alert_notification(
                        car,
                        _("One or more service provisionings failed to apply"),
                        _("Configuration Update Failed"),
                    )
                , thread_sensitive=False)
            else:
                new_alert = AlertHistory()
                new_alert.type = 18
                new_alert.car = car
                new_alert.command_id = car.command_id
                new_alert.additional_data = _(config_template["label"])
                new_alert.save()
                sync_to_async(
                    send_vehicle_alert_notification(
                        car,
                        _("Service Provisioning performed successfully!"),
                        _("Configuration Updated Successfully"),
                    )
                , thread_sensitive=False)

            tcu_config.ficosa_config["svc_provision"] = curr_ficosa_conf
            tcu_config.save()
        else:
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
    except Exception as e:
        logger.exception(e)


    car.command_requested = False
    car.save(update_fields=["command_requested", "command_result"])

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
