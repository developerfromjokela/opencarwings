import logging

from asgiref.sync import sync_to_async
from django.utils import timezone

from db.models import Car, AlertHistory, VehicleHealthInfo
import tculink.gdc_proto.ficosa.acp as acp
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _

logger = logging.getLogger("ficosa")


def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process vehicle health data
    """

    logger.info("Received new health report!")
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

    try:
        security_hdr, offset = acp.parser.decode_ficosa_vehicle_security_header(bin_data, 0)

        logger.debug("Security HDR: %s", security_hdr)
        data_timestamp, ts = acp.parser.decode_timestamp(bin_data, offset)
        offset += ts
        security_data, sec = acp.parser.decode_ficosa_vehicle_security_data(bin_data, offset)
        offset += sec
        logger.debug("Security DATA: %s", security_data)

        dtc_data, dtc = acp.parser.decode_ficosa_dtc_info(bin_data, offset)
        offset += dtc
        logger.debug("DTC DATA: %s", dtc_data)

        tpms_data, tpms = acp.parser.decode_ficosa_tire_pressure(bin_data, offset)
        offset += tpms
        logger.debug("TPMS DATA: %s", tpms_data)

        maint_data, maint = acp.parser.decode_acp_maintenance_alert(bin_data, offset)
        offset += maint
        logger.debug("MAINTENANCE: %s", maint_data)

        if car.veh_health is None:
            car.veh_health = VehicleHealthInfo()

        car.veh_health.dtc_timestamp = dtc_data.get("timestamp")
        car.veh_health.dtc_long = dtc_data.get("dtc_long")
        car.veh_health.dtc_short = dtc_data.get("dtc_short")

        car.veh_health.tpms_light = (tpms_data.get("light_status", 0) or 0) > 0
        car.veh_health.tpms_fr = tpms_data.get("fr") or 0
        car.veh_health.tpms_fl = tpms_data.get("fl") or 0
        car.veh_health.tpms_rr = tpms_data.get("rr") or 0
        car.veh_health.tpms_rl = tpms_data.get("rl") or 0

        car.veh_health.maintenance_alert = (maint_data.get("alert_status", 0) or 0) > 0
        car.veh_health.mileage = maint_data.get("mileage_km", 0) or 0
        car.veh_health.last_updated = timezone.now()
        car.veh_health.save()

        # also update odometer
        car.odometer = maint_data.get("mileage_km", 0) or 0
        car.save(update_fields=["odometer", "veh_health"])

    except Exception as e:
        logger.exception(e)

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
