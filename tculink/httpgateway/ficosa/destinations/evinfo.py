import logging

from asgiref.sync import sync_to_async
from django.utils import timezone

from db.models import Car, AlertHistory
from tculink.gdc_proto import GIDS_NEW_30kWh, GIDS_NEW_40kWh
from tculink.gdc_proto.ficosa.utils import command_to_destination_id
import tculink.gdc_proto.ficosa.acp as acp
from tculink.utils.notifications import send_vehicle_alert_notification_sync as send_vehicle_alert_notification
from django.utils.translation import gettext as _
logger = logging.getLogger("ficosa")


NON_AUTHABLE = [0x29, 0x2a, 0x2c, 0xdc]

def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process battery information
    """

    dest_id = command_to_destination_id(car.command_type)
    if destination_id not in NON_AUTHABLE and (not dest_id
            or dest_id != destination_id
            or not car.command_requested):
        logger.debug(f"Destination {destination_id} not authorized, details: {dest_id}, sid {source_id}, {car.command_id}, {car.command_requested}")
        # Acknowledge the command, but do not execute.
        # If ACK is not sent, the request will be repeated
        return b'ACK'


    app_info, offset = acp.parser.parse_ficosa_app_info(bin_data, 0)
    ev_info, __ = acp.parse_ev_info(bin_data, offset)

    # Update car EVInfo
    c_ev_info = car.ev_info
    c_ev_info.range_acon = ev_info["acon"]
    c_ev_info.range_acoff = ev_info["acoff"]
    c_ev_info.plugged_in = ev_info["pluggedin"]
    c_ev_info.charging = ev_info["charging"]
    c_ev_info.quick_charging = ev_info["quick_charging"]
    c_ev_info.ac_status = ev_info["acstate"]
    c_ev_info.charge_bars = ev_info["chargebars"]
    c_ev_info.cap_bars = ev_info["capacity_bars"]
    c_ev_info.car_running = ev_info["ignition"]
    c_ev_info.limit_chg_time = ev_info["1kw_chg"]
    c_ev_info.full_chg_time = ev_info["3kw_chg"]
    c_ev_info.obc_6kw = ev_info["6kw_chg"]
    c_ev_info.obc_6kw_avail = True

    if ev_info.get("parked", False):
        c_ev_info.car_gear = 0
    else:
        c_ev_info.car_gear = 1 if ev_info.get("direction_forward", False) else 2

    c_ev_info.soc = ev_info["soc"]
    c_ev_info.soc_display = ev_info["soc_display"]
    c_ev_info.gids = ev_info["gids"]
    c_ev_info.soh = ev_info["soh"]
    c_ev_info.last_updated = timezone.now()

    if c_ev_info.max_gids < 1:
        dcm_ver = acp_data["veh_desc"].get("dcm_ver", "")
        if dcm_ver == "TCU032":
            c_ev_info.max_gids = GIDS_NEW_30kWh
        elif dcm_ver == "TCU033":
            c_ev_info.max_gids = GIDS_NEW_40kWh

    c_ev_info.save()

    if destination_id not in NON_AUTHABLE or source_id == car.command_id:
        car.command_requested = False
        car.command_result = 0
        car.save()

    # Notification handling
    if destination_id == 0x29:
        new_alert = AlertHistory()
        new_alert.type = 3
        new_alert.car = car
        new_alert.command_id = car.command_id
        new_alert.save()
        sync_to_async(
            send_vehicle_alert_notification(
                car,
                _("Vehicle is unplugged. Please check the situation if necessary."),
                _("Charger unplugged notification")
            )
        , thread_sensitive=False)

    if destination_id == 0x2c or destination_id == 0xdc:
        new_alert = AlertHistory()
        new_alert.type = 97

        alert_msg = _("The A/C preconditioning command could not be executed. One of the "
                      "reasons behind such error could be: a) low state of charge b) command already executed c) TCU error.")
        alert_subject = _("A/C preconditioning error")

        error_present = app_info["flags"]["fail"] > 0

        # ac on
        if app_info["result"]["acResult"] == 1:
            alert_subject = _("A/C preconditioning started")
            alert_msg = _("A/C preconditioning has been successfully switched on")
            new_alert.type = 4
        # unknown
        elif app_info["itm2"]["acAutoOff"] == 2:
            alert_msg = _("The A/C preconditioning has finished unexpectedly")
            alert_subject = _("A/C precondition stopped")
            new_alert.type = 7
            new_alert.additional_data = alert_msg
        # timer off
        elif app_info["itm2"]["acAutoOff"] == 1:
            alert_msg = _("The A/C preconditioning is finished and switched off"
                          " after running certain amount of time.")
            alert_subject = _("A/C precondition finished")
            new_alert.type = 7

        # ac off
        if app_info["result"]["chargeStop"] == 1:
            alert_subject = _("A/C precondition stopped")
            alert_msg = _("A/C preconditioning has been successfully switched off")
            new_alert.type = 5
        # ac off, already off state
        elif app_info["result"]["chargeStop"] == 3:
            alert_subject = _("A/C precondition notification")
            alert_msg = _("A/C preconditioning already switched off")
            new_alert.additional_data = alert_msg
            new_alert.type = 5

        if error_present:
            alert_subject = _("A/C preconditioning fault")
            # ac on failure
            if app_info["result"]["acResult"] == 1:
                alert_msg = _("The vehicle failed to start A/C preconditioning")
            # autofinish
            if app_info["itm2"]["acAutoOff"] == 2:
                alert_msg = _("The A/C preconditioning has finished with error")
            # ac off
            elif app_info["result"]["chargeStop"] == 1:
                alert_msg = _("A/C preconditioning could not be switched off")

            alert_msg += f" (ECODE {app_info['raw'].hex()})"
            new_alert.additional_data = alert_msg
            new_alert.type = 97

        # debug this destination ID
        if destination_id == 0xdc:
            new_alert.additional_data += f" (UDCODE {hex(destination_id)} {app_info['raw'].hex()})"


        new_alert.car = car
        new_alert.command_id = car.command_id
        new_alert.save()

        sync_to_async(send_vehicle_alert_notification(
            car,
            alert_msg,
            alert_subject
        ), thread_sensitive=False)

    if destination_id == 0x2a:
        new_alert = AlertHistory()
        error_present = app_info["flags"]["fail"] != 0

        subject = _("Charging notification")
        new_alert.type = 1
        alert_message = f"charge_stop {app_info['flags']['fail']}"

        if app_info["flags"]["chargeFinish"] == 1:
            new_alert.type = 1
            alert_message = _("Vehicle has finished charging.")
            subject = _("Charge finish notification")
        elif app_info["flags"]["chargeFinish"] == 2:
            new_alert.type = 8
            alert_message = _("Vehicle has finished quick-charging.")
            subject = _("Quick-charge finish notification")

        if error_present:
            subject = _("Charge interruption notification")

            if app_info["result"]["chargeFinish"] == 1:
                alert_message = _("Charging has been stopped due to an interruption")
            elif app_info["result"]["chargeFinish"] == 2:
                alert_message = _("Quick-charging has been stopped due to an interruption")

            alert_message += f" (ECODE {app_info['raw'].hex()})"
            new_alert.additional_data = alert_message
            new_alert.type = 96

        new_alert.car = car
        new_alert.command_id = car.command_id
        new_alert.save()
        sync_to_async(send_vehicle_alert_notification(car, alert_message, subject), thread_sensitive=False)

    if destination_id == 0x2b or destination_id == 0x3e:
        new_alert = AlertHistory()
        new_alert.type = 2
        new_alert.car = car
        new_alert.command_id = car.command_id

        if app_info["result"]["chargeStart"] == 1 or app_info["result"]["gba"] == 1:
            subject = _("Charge start command executed")
            message = _("Charging command has been sent successfully. If vehicle did not start charging, "
                        "please check that the charging cable is connected and power is available.")
            if destination_id == 0x3e:
                new_alert.type = 11
        else:
            subject = _("Charge start command executed with failure")
            message = _("Charging command has been sent successfully, but the vehicle did not start charging.")
            new_alert.type = 96
            new_alert.additional_data = message

        if app_info["flags"]["fail"]> 0:
            subject = _("Charge start failure")
            message = _("Charge start command failed to execute.")
            message += f" (ECODE {app_info['raw'].hex()})"
            new_alert.type = 96
            new_alert.additional_data = message

        if destination_id == 0x3e:
            subject = f"80% {subject}"

        new_alert.save()
        sync_to_async(send_vehicle_alert_notification(
            car,
            message,
            subject), thread_sensitive=False)

    return b'ACK'