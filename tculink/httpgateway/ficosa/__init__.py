import io
import logging
from typing import Any

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.utils import timezone

from db.models import Car, CommandTimerSetting
from tculink.gdc_proto.ficosa import acp as ficosa_acp
from tculink.httpgateway.ficosa.destinations import DESTINATIONS

logger = logging.getLogger("ficosa")


def authenticate_car(veh_desc: dict, app_id: int) -> Car|None:
    try:
        car = Car.objects.get(vin=veh_desc.get("vin"), tcu_model=veh_desc.get("dcm"))

        # confirm TCU ID
        if veh_desc.get('dcm') != car.tcu_model:
            return None

        return car
    except Car.DoesNotExist:
        return None

def update_basic_car_info(acp_body: dict, car: Car) -> int|None:
    if "position" in acp_body and acp_body.get("position"):
        position = acp_body.get("position", {})
        car.location.lat = position.get("latitude", None)
        car.location.lon = position.get("longitude", None)
        car.location.home = position.get("home_status", False)
        car.location.last_updated = timezone.now()
        car.location.save()

    if "version" in acp_body:
        version = acp_body.get("version", {})
        car.vehicle_code1 = version.get("sw_version")
        car.vehicle_code2 = version.get("hw_1")
        car.vehicle_code3 = version.get("hw_2")
        car.vehicle_code4 = version.get("hw_3")

    if "veh_desc" in acp_body:
        if acp_body["veh_desc"].get("dcm_ver", None):
            car.tcu_ver = acp_body["veh_desc"].get("dcm_ver")

    car.last_connection = timezone.now()
    timer_id = None
    if car.command_payload is not None and car.command_payload.get("timer"):
        timer_id = car.command_payload.get("timer")
        car.command_payload = None
    car.save()
    return timer_id


def handle_request(request: WSGIRequest | Any) -> HttpResponse:
    bin_data = request.body
    if not bin_data:
        return HttpResponse(status=400)

    logger.debug(f"bin_data: {bin_data.hex()}")


    app_header, consumed = ficosa_acp.parser.decode_app_header(bin_data, 0)

    # FICOSA TCU uses this for non-standard ACP functions
    if app_header["special_flag"] != 1:
        logger.debug("special flag not set")
        return HttpResponse(status=400)

    app_id = app_header["app_id"]

    # "EV Auth-n-Confirm" request
    if app_id == 1:
        acp_body, offset = ficosa_acp.parse_auth_ev_pload(bin_data)
    # EV Request
    elif app_id == 3:
        acp_body, offset = ficosa_acp.parse_ev_request(bin_data)
    # Car Request
    elif app_id == 7:
        acp_body, offset = ficosa_acp.parse_car_request(bin_data)
    # Probe V2
    elif app_id == 30:
        acp_body, offset = ficosa_acp.parse_probe_request(bin_data)
    else:
        logger.debug(f"unknown, app_id: {app_id}")
        return HttpResponse(status=400)

    car = authenticate_car(acp_body["veh_desc"], app_id)

    if car is None:
        logger.debug(f"auth failed")
        return HttpResponse(status=401)

    timer_id = update_basic_car_info(acp_body, car)

    # just ACK probe data, analyze later
    if app_id == 30:
        return HttpResponse(status=200, content=io.BytesIO(b'ACK'), content_type="application/octet-stream")

    source_id = acp_body["source_id"]
    destination_id = acp_body["dest_id"]

    if destination_id not in DESTINATIONS:
        logger.debug(f"destination_id {destination_id} not in DESTINATIONS")
        return HttpResponse(status=400)

    bin_data = bin_data[offset:]
    resp_bin = DESTINATIONS[destination_id](bin_data, acp_body, car, source_id, destination_id)

    if timer_id is not None:
        try:
            timer_command = CommandTimerSetting.objects.get(pk=timer_id)
            timer_command.last_command_execution = timezone.now()
            timer_command.last_command_result = car.command_result
            if timer_command.timer_type == 0:
                timer_command.enabled = False
            timer_command.save()
        except CommandTimerSetting.DoesNotExist:
            logger.warning(f"timer {timer_id} does not exist")

    return HttpResponse(status=200, content=io.BytesIO(resp_bin), content_type="application/octet-stream")