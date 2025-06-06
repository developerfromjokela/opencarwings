import asyncio
import decimal
import logging
import os
import traceback

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from db.models import Car, AlertHistory
from tculink.gdc_proto import GIDS_NEW_24kWh, WH_PER_GID_GEN1
from tculink.gdc_proto.parser import parse_gdc_packet
from tculink.gdc_proto.responses import create_charge_status_response, create_charge_request_response, \
    create_ac_setting_response, create_ac_stop_response, create_config_read, auth_common_dest
from tculink.utils.notifications import send_vehicle_alert_notification
from django.utils.translation import gettext_lazy as _


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
    car.ev_info.param21 = ev_info.get("param21", 0)
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

                    logger.info(f"TCU Info: {tcu_info}")
                    try:
                        car = await get_car(tcu_info["vin"])
                        if tcu_info.get("tcu_id", None) != car.tcu_model:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            raise CommandError("TCU ID Mismatch")
                        if tcu_info.get("unit_id", None) != car.tcu_serial:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            raise CommandError("TCU Unit ID Mismatch")
                        if tcu_info.get("iccid", None) != car.iccid:
                            writer.write(create_charge_status_response(False))
                            await writer.drain()
                            raise CommandError("TCU ICCID Mismatch")

                        # skip auth and set as authenticated if check is disabled
                        authenticated = car.disable_auth
                        logger.info(f"TCU Authentication check status: {authenticated}")
                        # auth before anything
                        if parsed_data["message_type"][0] != 5 and not authenticated:
                            auth_data = parsed_data.get("auth", None)

                            if auth_data is None:
                                authenticated = False
                                writer.write(create_charge_status_response(False))
                                await writer.drain()
                                raise CommandError("TCU auth missing")

                            username = auth_data["user"]
                            password_hash = auth_data["pass"]

                            car_owner = await get_car_owner_info(car)

                            if username == car_owner.username or password_hash == car_owner.tcu_pass_hash:
                                authenticated = True
                            else:
                                authenticated = False
                                writer.write(create_charge_status_response(False))
                                await writer.drain()
                                raise CommandError("TCU auth mismatch")

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

                    if parsed_data.get("gps", None) is not None:
                        logger.info(f"GPS Data: {parsed_data['gps']}")
                        await set_gpsinfo(car, parsed_data["gps"])

                    if parsed_data["message_type"][0] == 1:
                        logger.info(f"Auth Data: {parsed_data['auth']}")
                        with open(f"datalog-msgtype1-{car.command_id}.bin", "wb") as file:
                            file.write(data)
                        if car.command_requested and car.command_result == -1:
                            logger.info(f"Command found: {car.command_id} {car.command_requested} {car.command_type} {car.command_payload} {car.command_request_time}")
                            if car.command_type == 1:
                                car.command_requested = False
                                car.command_result = 3
                                writer.write(create_charge_status_response(True))
                            elif car.command_type == 2:
                                car.command_requested = False
                                car.command_result = 3
                                writer.write(create_charge_request_response(True))
                            elif car.command_type == 3:
                                car.command_requested = False
                                car.command_result = 3
                                writer.write(create_ac_setting_response(True))
                            elif car.command_type == 4:
                                car.command_requested = False
                                car.command_result = 3
                                writer.write(create_ac_stop_response(True))
                            elif car.command_type == 5:
                                car.command_requested = False
                                car.command_result = 3
                                writer.write(create_config_read())
                            elif car.command_type == 6:
                                car.command_requested = False
                                car.command_result = 3
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
                        dtnow = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
                        with open(f"datalog-msgtype3-{car.command_id}-{dtnow}.bin", "wb") as file:
                            file.write(data)
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
                                alert_type = 97
                                if req_body["resultstate"] == 0x40:
                                    alert_type = 4
                                elif req_body["resultstate"] == 0x20:
                                    alert_type = 5
                                elif req_body["resultstate"] == 192:
                                    alert_type = 7
                                new_alert.type = alert_type
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                                alert_msg = _("The A/C preconditioning command could not be executed. One of the "
                                             "reasons behind such error could be: a) low state of charge b) command already executed c) TCU error.")
                                alert_subject = _("A/C preconditioning error")
                                if alert_type == 4:
                                    alert_subject = _("A/C preconditioning started")
                                    alert_msg = _("A/C preconditioning has been successfully switched on")
                                if alert_type == 5:
                                    alert_subject = _("A/C precondition stopped")
                                    alert_msg = _("A/C preconditioning has been successfully switched off")
                                if alert_type == 7:
                                    alert_msg = _("The A/C preconditioning is finished and switched off"
                                                 " after running certain amount of time.")
                                    alert_subject = _("A/C precondition finished")
                                await send_vehicle_alert_notification(
                                    car,
                                    alert_msg,
                                    alert_subject
                                )

                            if body_type == "remote_stop":
                                new_alert = AlertHistory()
                                alert_message = _("A/C preconditioning is finished")
                                subject = _("A/C precondition notification")

                                if req_body["alertstate"] == 4 or req_body["alertstate"] == 0x44:
                                    new_alert.type = 1
                                    alert_message = _("Vehicle has finished charging.")
                                    subject = _("Charge finish notification")
                                elif req_body["alertstate"] == 8:
                                    new_alert.type = 8
                                    alert_message = _("Vehicle has finished quick-charging.")
                                    subject = _("Quick-charge finish notification")
                                else:
                                    new_alert.type = 7
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(car, alert_message, subject)

                            if body_type == "charge_result":
                                new_alert = AlertHistory()
                                new_alert.type = 2
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()
                                await send_vehicle_alert_notification(
                                    car,
                                    _("Charging command has been sent successfully. If vehicle did not start charging, "
                                     "please check that the charging cable is connected and power is available."),
                                    _("Charge start command executed"))
                    elif parsed_data["message_type"][0] == 5:
                        if not authenticated:
                            break
                        with open(f"datalog-msgtype5-{car.command_id}.bin", "wb") as file:
                            file.write(data)
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