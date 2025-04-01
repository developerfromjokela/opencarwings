import asyncio
import traceback
from datetime import datetime
import logging
import os
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone
from db.models import Car, AlertHistory
from tculink.gdc_proto.parser import parse_gdc_packet
from tculink.gdc_proto.responses import create_charge_status_response, create_charge_request_response, \
    create_ac_setting_response, create_ac_stop_response, create_config_read
from asgiref.sync import sync_to_async

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
def set_evinfo(car, ev_info):
    car.ev_info.range_acon = ev_info.get("acon", None)
    car.ev_info.range_acoff = ev_info.get("acoff", None)
    car.ev_info.plugged_in = ev_info.get("pluggedin", False)
    car.ev_info.charging = ev_info.get("charging", False)
    car.ev_info.ac_status = ev_info.get("acstate", False)
    car.ev_info.soc = ev_info.get("soc", 0)
    car.ev_info.soh = ev_info.get("soh", 0)
    car.ev_info.cap_bars = ev_info.get("capacity_bars", 0)
    car.ev_info.charge_bars = ev_info.get("chargebars", 0)
    car.ev_info.eco_mode = False
    car.ev_info.gids = ev_info.get("gids", 0)
    car.ev_info.gids_relative = ev_info.get("gids_relative", 0)
    car.ev_info.max_gids_relative = 0
    car.ev_info.full_chg_time = ev_info.get("full_chg", 0)
    car.ev_info.limit_chg_time = ev_info.get("limit_chg", 0)
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

                        if car.vehicle_code1 != tcu_info["vehicle_code1"]:
                            car.vehicle_code1 = tcu_info["vehicle_code1"]
                        if car.vehicle_code2 != tcu_info["vehicle_code2"]:
                            car.vehicle_code2 = tcu_info["vehicle_code2"]
                        if car.vehicle_code3 != tcu_info["vehicle_code3"]:
                            car.vehicle_code3 = tcu_info["vehicle_code3"]
                        if car.vehicle_code4 != tcu_info["vehicle_code4"]:
                            car.vehicle_code4 = tcu_info["vehicle_code4"]
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
                            else:
                                logger.info(f"Unknown command: {car.command_type}")
                                writer.write(create_charge_status_response(False))
                                logger.info("Write failure response and change request status")
                                car.command_requested = False
                                car.command_result = 1
                        else:
                            logger.info("No command or another in progress, send success false")
                            writer.write(create_charge_status_response(False))

                    if parsed_data["message_type"][0] == 3:
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
                                await set_evinfo(car, req_body)

                            if body_type == "cp_remind":
                                new_alert = AlertHistory()
                                new_alert.type = 3
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                                car_owner = await get_car_owner_info(car)
                                if car_owner.email_notifications:
                                    ev_info = await get_evinfo(car)
                                    location = await get_location(car)

                                    text_content = render_to_string(
                                        "emails/vehicle_alert.txt",
                                        context={
                                            "alert": "Vehicle is unplugged. Please check the situation if necessary.",
                                            "vehicle": car.nickname,
                                            "range_acon": ev_info.range_acon,
                                            "range_acoff": ev_info.range_acoff,
                                            "soc": ev_info.soc,
                                            "pluggedin": "yes" if ev_info.plugged_in else "no",
                                            "athome": "yes" if location.home else "no"
                                        },
                                    )

                                    send_mail(
                                        "Charger unplugged notification - OpenCARWINGS",
                                        text_content,
                                        settings.DEFAULT_FROM_EMAIL,
                                        [car_owner.email],
                                        fail_silently=True
                                    )

                            if body_type == "ac_result":
                                new_alert = AlertHistory()
                                if req_body["resultstate"] == 0x40:
                                    new_alert.type = 4
                                elif req_body["resultstate"] == 0x20:
                                    new_alert.type = 5
                                elif req_body["resultstate"] == 192:
                                    new_alert.type = 7
                                else:
                                    new_alert.type = 97
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                            if body_type == "remote_stop":
                                new_alert = AlertHistory()
                                if req_body["alertstate"] == 4:
                                    new_alert.type = 1
                                else:
                                    new_alert.type = 7
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                                car_owner = await get_car_owner_info(car)
                                if car_owner.email_notifications:
                                    ev_info = await get_evinfo(car)
                                    location = await get_location(car)

                                    text_content = render_to_string(
                                        "emails/vehicle_alert.txt",
                                        context={
                                            "alert": "Vehicle has finished charging." if req_body["alertstate"] == 4 else "A/C preconditioning is finished",
                                            "vehicle": car.nickname,
                                            "range_acon": ev_info.range_acon,
                                            "range_acoff": ev_info.range_acoff,
                                            "soc": ev_info.soc,
                                            "pluggedin": "yes" if ev_info.plugged_in else "no",
                                            "athome": "yes" if location.home else "no"
                                        },
                                    )

                                    send_mail(
                                        "Charge finish notification - OpenCARWINGS" if req_body["alertstate"] == 4 else "A/C precondition notification - OpenCARWINGS",
                                        text_content,
                                        settings.DEFAULT_FROM_EMAIL,
                                        [car_owner.email],
                                        fail_silently=True
                                    )

                            if body_type == "charge_result":
                                new_alert = AlertHistory()
                                new_alert.type = 2
                                new_alert.car = car
                                new_alert.command_id = car.command_id
                                await sync_to_async(new_alert.save)()

                    if parsed_data["message_type"][0] == 5 and authenticated:
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