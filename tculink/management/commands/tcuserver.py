import asyncio
import decimal
import logging
import os
import traceback

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from db.models import Car, AlertHistory, CommandTimerSetting
from tculink.gdc_proto import GIDS_NEW_24kWh, WH_PER_GID_GEN1
from tculink.gdc_proto.parser import parse_gdc_packet
from tculink.gdc_proto.responses import create_charge_status_response, create_charge_request_response, \
    create_ac_setting_response, create_ac_stop_response, create_config_read, auth_common_dest
from tculink.utils.notifications import send_vehicle_alert_notification
from django.utils.translation import gettext as _


# Configure logging
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'tcuserver.log')),
        logging.StreamHandler()  # This keeps console output as well
    ]
)
logger = logging.getLogger(__name__)


@sync_to_async
def get_car(vin_id):
    return Car.objects.get(vin=vin_id)

@sync_to_async
def get_commandtimersetting(id):
    return CommandTimerSetting.objects.get(pk=id)

@sync_to_async
def get_car_owner_info(car):
    return car.owner

@sync_to_async
def set_evinfo(car, ev_info, tcu_info):
    if car.ev_info.max_gids == 0:
        if tcu_info['vehicle_descriptor'] == 0x02 or tcu_info['vehicle_descriptor'] == 0x92:
            car.ev_info.max_gids = GIDS_NEW_24kWh

    car.ev_info.range_acon = int(decimal.Decimal(
        (ev_info.get("acon", 0)*((ev_info.get("gids", 0)*WH_PER_GID_GEN1)/10000))).__round__(0))
    car.ev_info.range_acoff = int(decimal.Decimal(
        (ev_info.get("acoff", 0)*((ev_info.get("gids", 0)*WH_PER_GID_GEN1)/10000))).__round__(0))
    car.ev_info.plugged_in = ev_info.get("pluggedin", False)
    car.ev_info.charge_finish = ev_info.get("charging_finish", False)
    car.ev_info.quick_charging = ev_info.get("quick_charging", False)
    car.ev_info.charging = True if car.ev_info.quick_charging else ev_info.get("charging", False)


    if car.ev_info.charge_finish:
        car.ev_info.charging = False
        car.ev_info.quick_charging = False

    car.ev_info.ac_status = ev_info.get("acstate", False)
    car.ev_info.soc = ev_info.get("soc", 0)
    car.ev_info.soh = ev_info.get("soh", 0)
    car.ev_info.cap_bars = ev_info.get("capacity_bars", 0)
    car.ev_info.charge_bars = ev_info.get("chargebars", 0)
    car.ev_info.eco_mode = False
    car.ev_info.gids = ev_info.get("gids", 0)
    car.ev_info.counter = ev_info.get("counter", 0)
    car.ev_info.soc_display = 0

    # Calc "display" SOC
    if car.ev_info.max_gids > 0 and car.ev_info.soh > 0 and (tcu_info['vehicle_descriptor'] != 0x02 or car.ev_info.force_soc_display):
        car.ev_info.soc_display = (
            ev_info.get("gids", 0) / (car.ev_info.max_gids * (car.ev_info.soh/100))
        ) * 100.0

    car.ev_info.full_chg_time = ev_info.get("full_chg", 0)
    car.ev_info.limit_chg_time = ev_info.get("limit_chg", 0)
    car.ev_info.obc_6kw = ev_info.get("6kw_chg", 0)
    car.ev_info.obc_6kw_avail = ev_info.get("obc_6kw_exist", False)
    car.ev_info.batt_heater_avail = ev_info.get("batt_heat_exist", False)
    car.ev_info.batt_heater_status = ev_info.get("batt_heat_active", False)
    car.ev_info.wh_content = ev_info.get("gids", 0)*WH_PER_GID_GEN1
    car.ev_info.car_running = ev_info.get("ignition", False)
    if ev_info.get("parked", False):
        car.ev_info.car_gear = 0
    else:
        car.ev_info.car_gear = 1 if ev_info.get("direction_forward", False) else 2
    car.ev_info.last_updated = timezone.now()
    car.ev_info.save()

@sync_to_async
def set_tcuconfig(car, car_config):
    car.tcu_configuration.dial_code = car_config.get("dial_code", None)
    car.tcu_configuration.apn = car_config.get("apn_name", None)
    car.tcu_configuration.apn_user = car_config.get("apn_user", None)
    car.tcu_configuration.apn_password = car_config.get("apn_pass", None)
    car.tcu_configuration.dns1 = car_config.get("dns1", None)
    car.tcu_configuration.dns2 = car_config.get("dns2", None)
    car.tcu_configuration.server_url = car_config.get("server_url", None)
    car.tcu_configuration.proxy_url = car_config.get("proxy_url", None)
    car.tcu_configuration.connection_type = car_config.get("gprs_type", None)
    car.tcu_configuration.last_updated = timezone.now()
    car.tcu_configuration.save()

@sync_to_async
def set_gpsinfo(car, gps_info):
    car.location.lat = gps_info.get("latitude", None)
    car.location.lon = gps_info.get("longitude", None)
    car.location.home = gps_info.get("home_status", False)
    car.location.last_updated = timezone.now()
    car.location.save()

@sync_to_async
def get_evinfo(car):
    return car.ev_info

@sync_to_async
def get_location(car):
    return car.location

class Command(BaseCommand):
    help = "Start TCU socket server"

    def add_arguments(self, parser):
        parser.add_argument("host", type=str)

    async def handle_client(self, reader, writer):
        """Handle individual client connections"""
        try:
            authenticated = False
            while True:
                data = await reader.read(1024)  # Read up to 1024 bytes
                if not data:
                    logger.info("Connection closed")
                    break

                try:
                    parsed_data = parse_gdc_packet(data)

                    if parsed_data.get("tcu", None) is None:
                        raise CommandError("No TCU info received")

                    tcu_info = parsed_data["tcu"]

                    if tcu_info["vin"] is None:
                        raise CommandError("No VIN received")

                    logger.info(f"TCU Payload hex: {data.hex()}")
                    logger.info(f"TCU Info: {tcu_info}")
                    try:
                        car = await get_car(tcu_info["vin"])
                        if tcu_info.get("tcu_id", None) != car.tcu_model:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            new_alert = AlertHistory()
                            new_alert.type = 99
                            new_alert.additional_data = _("TCU ID does not match with specified ID, please double check!")
                            new_alert.car = car
                            new_alert.command_id = car.command_id
                            await sync_to_async(new_alert.save)()
                        elif tcu_info.get("unit_id", None) != car.tcu_serial:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            new_alert = AlertHistory()
                            new_alert.type = 99
                            new_alert.additional_data = _("Navi ID does not match with specified ID, please double check!")
                            new_alert.car = car
                            new_alert.command_id = car.command_id
                            await sync_to_async(new_alert.save)()
                        elif tcu_info.get("iccid", None) != car.iccid:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            new_alert = AlertHistory()
                            new_alert.type = 99
                            new_alert.additional_data = _("Sim ID does not match with specified ID, please double check!")
                            new_alert.car = car
                            new_alert.command_id = car.command_id
                            await sync_to_async(new_alert.save)()
                        else:
                            # skip auth and set as authenticated if check is disabled
                            authenticated = car.disable_auth
                            logger.info(f"TCU Authentication check status: {authenticated}")
                            # auth before anything
                            if parsed_data["message_type"][0] != 5 and not authenticated:
                                auth_data = parsed_data.get("auth", None)

                                if auth_data is None:
                                    writer.write(create_charge_status_response(False))
                                    await writer.drain()
                                    new_alert = AlertHistory()
                                    new_alert.type = 99
                                    new_alert.additional_data = _(
                                        "Authentication failed, username or password is missing! Please sign in using navigation unit.")
                                    new_alert.car = car
                                    new_alert.command_id = car.command_id
                                    await sync_to_async(new_alert.save)()
                                else:
                                    username = auth_data["user"]
                                    password_hash = auth_data["pass"]

                                    car_owner = await get_car_owner_info(car)

                                    if username == car_owner.username or password_hash == car_owner.tcu_pass_hash:
                                        authenticated = True
                                    else:
                                        writer.write(create_charge_status_response(False))
                                        await writer.drain()
                                        new_alert = AlertHistory()
                                        new_alert.type = 99
                                        new_alert.additional_data = _(
                                            "Authentication failed, username or password is incorrect! Please sign in using navigation unit.")
                                        new_alert.car = car
                                        new_alert.command_id = car.command_id
                                        await sync_to_async(new_alert.save)()

                        car.last_connection = timezone.now()

                        car.vehicle_code1 = tcu_info["vehicle_descriptor"]
                        car.vehicle_code2 = tcu_info["vehicle_code1"]
                        car.vehicle_code3 = tcu_info["vehicle_code2"]
                        car.vehicle_code4 = tcu_info["vehicle_code3"]
                        car.tcu_ver = tcu_info["sw_version"]
                    except Car.DoesNotExist:
                        writer.write(create_charge_status_response(False))
                        await writer.drain()
                        raise CommandError("No car found")

                    if not authenticated:
                        car.command_result = 1
                        car.command_requested = False
                        await sync_to_async(car.save)()
                        await writer.drain()
                        return

                    if parsed_data.get("gps", None) is not None:
                        logger.info(f"GPS Data: {parsed_data['gps']}")
                        await set_gpsinfo(car, parsed_data["gps"])

                    if parsed_data["message_type"][0] == 1:
                        logger.info(f"Auth Data: {parsed_data['auth']}")
                        if car.command_requested and car.command_result == -1:
                            logger.info(f"Command found: {car.command_id} {car.command_requested} {car.command_type} {car.command_payload} {car.command_request_time}")
                            car.command_result = 3
                            car.command_requested = False
                            if car.command_type == 1:
                                writer.write(create_charge_status_response(True))
                            elif car.command_type == 2:
                                writer.write(create_charge_request_response(True))
                            elif car.command_type == 3:
                                writer.write(create_ac_setting_response(True))
                            elif car.command_type == 4:
                                writer.write(create_ac_stop_response(True))
                            elif car.command_type == 5:
                                writer.write(create_config_read())
                            elif car.command_type == 6:
                                writer.write(auth_common_dest())
                            else:
                                logger.info(f"Unknown command: {car.command_type}")
                                writer.write(create_charge_status_response(False))
                                logger.info("Write failure response and change request status")
                                car.command_requested = False
                                car.command_result = 1

                        else:
                            logger.info("No command or another in progress, send success false")
                            writer.write(create_charge_status_response(False))
                    elif parsed_data["message_type"][0] == 3:
                        logger.info(f"Auth Data: {parsed_data['auth']}")
                        body_type = parsed_data["body_type"]
                        logger.info(f"Body Type: {body_type}")

                        car.command_result = 0

                        if parsed_data["body"] is not None:
                            req_body = parsed_data["body"]
                            if body_type != "config_read":
                                await set_evinfo(car, req_body, tcu_info)

                            if body_type == "cp_remind":
                                new_alert = AlertHistory()
                                new_alert.type = 3
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(
                                    car,
                                    _("Vehicle is unplugged. Please check the situation if necessary."),
                                    _("Charger unplugged notification")
                                )

                            if body_type == "ac_result":
                                new_alert = AlertHistory()
                                new_alert.type = 97

                                alert_msg = _("The A/C preconditioning command could not be executed. One of the "
                                             "reasons behind such error could be: a) low state of charge b) command already executed c) TCU error.")
                                alert_subject = _("A/C preconditioning error")

                                error_present = req_body["error_notification"] > 0

                                # ac on
                                if req_body["pri_ac_req_result"] == 1:
                                    alert_subject = _("A/C preconditioning started")
                                    alert_msg = _("A/C preconditioning has been successfully switched on")
                                    new_alert.type = 4
                                # unknown
                                elif req_body["pri_ac_req_result"] == 2:
                                    alert_msg = _("The A/C preconditioning has finished unexpectedly")
                                    alert_subject = _("A/C precondition stopped")
                                    new_alert.type = 7
                                    new_alert.additional_data = alert_msg
                                # timer off
                                elif req_body["pri_ac_req_result"] == 3:
                                    alert_msg = _("The A/C preconditioning is finished and switched off"
                                                 " after running certain amount of time.")
                                    alert_subject = _("A/C precondition finished")
                                    new_alert.type = 7


                                # ac off
                                if req_body["pri_ac_stop_result"] == 2:
                                    alert_subject = _("A/C precondition stopped")
                                    alert_msg = _("A/C preconditioning has been successfully switched off")
                                    new_alert.type = 5
                                # ac off, already off state
                                elif req_body["pri_ac_stop_result"] == 1:
                                    alert_subject = _("A/C precondition notification")
                                    alert_msg = _("A/C preconditioning already switched off")
                                    new_alert.additional_data = alert_msg
                                    new_alert.type = 5


                                if error_present:
                                    alert_subject = _("A/C preconditioning fault")
                                    # ac on failure
                                    if req_body["pri_ac_req_result"] == 1:
                                        alert_msg = _("The vehicle failed to start A/C preconditioning")
                                    # unknown failure
                                    elif req_body["pri_ac_req_result"] == 2:
                                        alert_msg = _("The A/C preconditioning has finished with error")
                                    # timer off
                                    elif req_body["pri_ac_req_result"] == 3:
                                        alert_msg = _("The A/C preconditioning is finished and switched off"
                                                      " because of an error")
                                    # ac off
                                    elif req_body["pri_ac_stop_result"] == 2:
                                        alert_msg = _("A/C preconditioning could not be switched off")
                                    # ac off, already off state
                                    elif req_body["pri_ac_stop_result"] == 1:
                                        alert_msg = _("A/C preconditioning already switched off")

                                    alert_msg += f" (ECODE {req_body['error_notification']})"
                                    new_alert.additional_data = alert_msg
                                    new_alert.type = 97

                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                                await send_vehicle_alert_notification(
                                    car,
                                    alert_msg,
                                    alert_subject
                                )

                            if body_type == "remote_stop":
                                new_alert = AlertHistory()
                                error_present = req_body["error_notification"] > 0

                                if req_body["charge_stop"] != 0:
                                    subject = _("Charging notification")
                                    new_alert.type = 96
                                    alert_message = f"charge_stop {req_body['charge_stop']}"

                                    if req_body["charge_stop"] == 1:
                                        new_alert.type = 1
                                        alert_message = _("Vehicle has finished charging.")
                                        subject = _("Charge finish notification")
                                    elif req_body["charge_stop"] == 2:
                                        new_alert.type = 8
                                        alert_message = _("Vehicle has finished quick-charging.")
                                        subject = _("Quick-charge finish notification")

                                    if error_present:
                                        subject = _("Charge interruption notification")

                                        if req_body["charge_stop"] == 1:
                                            alert_message = _("Charging has been stopped due to an interruption")
                                        elif req_body["charge_stop"] == 2:
                                            alert_message = _("Quick-charging has been stopped due to an interruption")

                                        alert_message += f" (ECODE {req_body['error_notification']})"
                                        new_alert.additional_data = alert_message
                                        new_alert.type = 96
                                else:
                                    subject = _("A/C precondition notification")
                                    new_alert.type = 97
                                    alert_message = f"pri_ac_req_result {req_body['pri_ac_req_result']}"

                                    if req_body["pri_ac_req_result"] == 3:
                                        alert_message = _("The A/C preconditioning is finished and switched off"
                                                      " after running certain amount of time.")
                                        subject = _("A/C precondition finished")
                                        new_alert.type = 7

                                    if error_present:
                                        subject = _("A/C preconditioning fault")

                                        if req_body["pri_ac_req_result"] == 3:
                                            alert_message = _("The A/C preconditioning is finished and switched off"
                                                          " because of an error")

                                        alert_message += f" (ECODE {req_body['error_notification']})"
                                        new_alert.additional_data = alert_message
                                        new_alert.type = 97


                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(car, alert_message, subject)

                            if body_type == "charge_result":
                                new_alert = AlertHistory()
                                new_alert.type = 2
                                new_alert.car = car
                                new_alert.command_id = car.command_id

                                if req_body["charge_request_result"] == 1:
                                    subject = _("Charge start command executed")
                                    message = _("Charging command has been sent successfully. If vehicle did not start charging, "
                                         "please check that the charging cable is connected and power is available.")
                                else:
                                    subject = _("Charge start command executed with failure")
                                    message = _("Charging command has been sent successfully, but the vehicle did not start charging.")
                                    new_alert.type = 96
                                    new_alert.additional_data = message

                                if req_body["error_notification"] > 0:
                                    subject = _("Charge start failure")
                                    message = _("Charge start command failed to execute.")
                                    message += f" (ECODE {req_body['error_notification']})"
                                    new_alert.type = 96
                                    new_alert.additional_data = message

                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(
                                    car,
                                    message,
                                    subject)

                            if body_type == "battery_heat":
                                # TODO: capture resultstate to determine battery heater status
                                logger.warning("Battery heat! Resultstate: %d, alertstate: %d", req_body["resultstate"], req_body["alertstate"])
                                new_alert = AlertHistory()
                                new_alert.additional_data = f"{req_body['resultstate']},{req_body['alertstate']}"
                                new_alert.type = 9 if req_body.get('batt_heat_active', False) else 10
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(
                                    car,
                                    _("Battery heater notification"),
                                    _("Battery heater has turned on") if req_body.get('batt_heat_active', False) else _("Battery heater has turned off")
                                )
                    elif parsed_data["message_type"][0] == 5:
                        car.command_result = 0

                        new_alert = AlertHistory()
                        new_alert.type = 6
                        new_alert.car = car
                        new_alert.command_id = car.command_id
                        await sync_to_async(new_alert.save)()

                        car_config = parsed_data["body"]
                        logger.info(f"Car Config: {car_config}")
                        await set_tcuconfig(car, car_config)
                    else:
                        raise Exception("Invalid message type")

                    await sync_to_async(car.save)()
                    try:
                        timer_command = await get_commandtimersetting(car.command_id)
                        timer_command.last_command_execution = timezone.now()
                        timer_command.last_command_result = car.command_result
                        if timer_command.timer_type == 0:
                            timer_command.enabled = False
                        await sync_to_async(timer_command.save)()
                    except CommandTimerSetting.DoesNotExist:
                        ...
                    await writer.drain()
                except Exception as e:
                    logger.error("Processing packet failed")
                    logger.error(e)
                    logger.error(traceback.format_exc())
                    # GDC packets are generally under 1024 bytes, limit to prevent spam
                    if len(data) < 1024:
                        logger.info("Response logged to file for analysis")
                        dtnow = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
                        with open(f"logs/datalog-unknownmsg-{dtnow}.bin", "wb") as file:
                            file.write(data)

        except Exception as e:
            logger.error(f"Error handling client: {e}")
            logger.error(traceback.format_exc())
        finally:
            writer.close()
            await writer.wait_closed()

    async def start_server(self, host='127.0.0.1', port=55230):
        """Start the TCP server"""
        try:
            server = await asyncio.start_server(
                self.handle_client, host, port
            )
            addr = server.sockets[0].getsockname()
            logger.info(f"Server running on {addr[0]}:{addr[1]}")
            self.stdout.write(self.style.SUCCESS(
                f"Server running on {addr[0]}:{addr[1]}"
            ))

            async with server:
                await server.serve_forever()

        except Exception as e:
            raise CommandError(f"Server error: {e}")

    def handle(self, *args, **options):
        """Handle the command execution"""
        host = options["host"]
        try:
            asyncio.run(self.start_server(host=host))
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            self.stdout.write("Server stopped by user")
        except Exception as e:
            logger.error(f"Error: {e}")
            raise CommandError(f"Error: {e}")