import logging
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from db.models import Car
from tculink.carwings_proto.dataobjects import build_autodj_payload, construct_dms_coordinate

from django.utils.translation import gettext as _

from tculink.carwings_proto.utils import encode_utf8, xml_coordinate_to_float
from tculink.coordinators.stub import send_command_using_provider

logger = logging.getLogger("carwings_abrp")

def no_route_set_resp(channel_id) -> bytes:
    return build_autodj_payload(
        0,
        channel_id,
        [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8(_('No Destination'), limit=0x20),
                'dynamicDataField2': b'',
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                "bigDynamicField7": encode_utf8(_('No Destination Set')),
                "bigDynamicField8": encode_utf8(
                    _('To calculate charging stops along your route, please set a destination in your navigation or send one from your phone.')),
                "iconField": 0x0000,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 0,
                "unknownLongId4": 0x0000,
                "flag5": 0,
                "flag6": 0,
                "12byteField1": b'\x00' * 12,
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                "flag8": 0,
                "imageDataField": bytearray()
            }
        ],
        {
            "type": 6,
            "data": b'\x01',
        },
        extra_fields={
            'stringField1': _("No Destination"),
            'stringField2': _("No Destination"),
            "mode0_processedFieldCntPos": 1,
            "mode0_countOfSomeItems3": 1,
            "countOfSomeItems": 1
        }
    )

def no_evdata_resp(channel_id) -> bytes:
    return build_autodj_payload(
        0,
        channel_id,
        [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8(_('Updating battery info'), limit=0x20),
                'dynamicDataField2': b'',
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                "bigDynamicField7": encode_utf8(_('Updating current battery information')),
                "bigDynamicField8": encode_utf8(
                    _('Before planning the route, current battery information needs to be updated. Please wait while it is updated, and try again within 1 to 2 minutes.')),
                "iconField": 0x0000,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 0,
                "unknownLongId4": 0x0000,
                "flag5": 0,
                "flag6": 0,
                "12byteField1": b'\x00' * 12,
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                "flag8": 0,
                "imageDataField": bytearray()
            }
        ],
        {
            "type": 6,
            "data": b'\x01',
        },
        extra_fields={
            'stringField1': _("Updating current battery information"),
            'stringField2': _("Updating current battery information"),
            "mode0_processedFieldCntPos": 1,
            "mode0_countOfSomeItems3": 1,
            "countOfSomeItems": 1
        }
    )

def plan_error_resp(channel_id, error_msg, long_msg) -> bytes:
    return build_autodj_payload(
        0,
        channel_id,
        [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8(error_msg, limit=31),
                'dynamicDataField2': b'',
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                "bigDynamicField7": encode_utf8(long_msg),
                "bigDynamicField8": encode_utf8(long_msg),
                "iconField": 0x0000,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 0,
                "unknownLongId4": 0x0000,
                "flag5": 0,
                "flag6": 0,
                "12byteField1": b'\x00' * 12,
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                "flag8": 0,
                "imageDataField": bytearray()
            }
        ],
        {
            "type": 6,
            "data": b'\x01',
        },
        extra_fields={
            'stringField1': _("ABRP Error"),
            'stringField2': _("ABRP Error"),
            "mode0_processedFieldCntPos": 1,
            "mode0_countOfSomeItems3": 1,
            "countOfSomeItems": 1
        }
    )

def get_vehicle_route(xml_data) -> tuple[list, bool]:
    if (xml_data.get('operation_info', None) is not None
            and xml_data['operation_info'].get('via_destination', None) is not None
            and xml_data['operation_info']['via_destination']['guide_status'] not in ["dst", "no_guide"]):
        points_count = int(xml_data['operation_info']['via_destination'].get('set_number') or 0)
        points = [None] * points_count
        waypoints = xml_data['operation_info']['via_destination']["waypoints"]
        min_highways = xml_data['operation_info']['via_destination']["search_condition"] == "hwy"
        for point in waypoints:
            if point["coordinates"] is not None:
                new_point = {
                    "location": xml_coordinate_to_float(point["coordinates"]),
                    "name": point["name"]
                }
                if point["type"] is not None and "via" in point["type"]:
                    idx = int(re.sub('\\D', '', point['type']))-1
                    if idx <= len(points)-1:
                        points[idx] = new_point
                    else:
                        points.append(new_point)
                else:
                    points[-1] = new_point
        return [p for p in points if p is not None], min_highways
    return [], False

def make_abrp_plan(car: Car, points, avoid_highways=False):
    vehicle_code = ""
    if car.tcu_type == "continental2012":
        vehicle_code = "nissan:leaf:12:24:other"
        if car.vin.startswith("VS"): # ENV200
            vehicle_code = "nissan:env200:12:24:none"
            if car.ev_info.max_gids > 281:
                vehicle_code = "nissan:env200:16:30:none"
            if car.ev_info.max_gids > 350:
                vehicle_code = "nissan:env200:18:40:none"
    elif car.tcu_type == "ficosa2016":
        vehicle_code = "nissan:leaf:16:30:other"
        if car.vin.startswith("VS"):  # ENV200
            vehicle_code = "nissan:env200:18:40:none"
            if car.ev_info.max_gids < 400:
                vehicle_code = "nissan:env200:16:30:none"
        elif car.ev_info.max_gids > 500:
            vehicle_code = "nissan:leaf:19:62:eplus"
        elif car.ev_info.max_gids > 300:
            vehicle_code = "nissan:leaf:18:40:other"

    return requests.post('https://api.iternio.com/2/abrp/plan', json={
        'destinations': [
            {
                'location': {
                'type': 'COORDINATES',
                'lat': x['location'][0],
                'long': x['location'][1]
                },
                'timeSettings': {},
                'energySettings': {},
                'name': x['name'],
            }
            for x in points
        ],
        "vehicle": {
            "identifier": {
                "type": "TYPECODE",
                "value": vehicle_code,
            },
            "currentSocFrac": round(car.ev_info.soc_display, 2)/100,
            "degradationFrac": car.ev_info.soh/100,
            "batteryCapacityWh": car.ev_info.wh_content
        },
        "avoid": {"borders": False, "ferries": False, "highways": avoid_highways, "tolls": False},
        "charging": {
            "connectorTypes": ["CHADEMO"],
            "stopPreference": "OPTIMAL",
            "minimumChargerArrivalSocFrac": 0.2,
            "minimumDestinationSocFrac": 0.2,
            "maximumChargingSocFrac": 0.9,
            "preferredMinimumStallCount": 1
        },
        "weather": {"type": "SEASONAL"},
        "resultOptions": {"currency": "EUR", "alternatives": {"type": "ROUTES"}},
        "clientContext": {
            "version": 1,
            "currentSocSource": "live_data",
            "destinations": []
        }
    }, headers={"x-api-key": settings.ITERNIO_API_KEY}).json()


def handle_abrp(xml_data, returning_xml, channel_id, car: Car, page):
    vehicle_route, min_highways = get_vehicle_route(xml_data)
    car_coordinate = (car.location.lat, car.location.lon)
    if (xml_data.get('base_info', None) is not None
            and xml_data['base_info'].get('vehicle', None) is not None
            and xml_data['base_info']['vehicle'].get('coordinates', None) is not None
            and xml_data['base_info']['vehicle']['coordinates'].get('datum', '') == "wgs84"):
        car_coordinate = xml_coordinate_to_float(xml_data['base_info']['vehicle']['coordinates'])

    if len(vehicle_route) == 0:
        # check for sent location
        if car.send_to_car_location.exists():
            latest_sent = car.send_to_car_location.all().order_by('-created_at').first()
            point_name = latest_sent.name
            if point_name is None:
                point_name = "Send To Car Location"
            vehicle_route.append({
                "location": (latest_sent.lat, latest_sent.lon),
                "name": point_name
            })

    if len(vehicle_route) == 0:
        return [("ABRP", no_route_set_resp(channel_id))]

    period = 5 if car.ev_info.car_running else 30
    if car.ev_info.last_updated is None or car.ev_info.last_updated < timezone.now() - timedelta(minutes=period):
        if car.command_requested:
            return [("ABRP", no_evdata_resp(channel_id))]
        car.periodic_refresh_running = 5
        car.save(update_fields=['periodic_refresh_running'])
        try:
            send_command_using_provider(1, None, car)
        except Exception as e:
            logger.exception(e)
            return [("ABRP", plan_error_resp(channel_id, _("Cannot update battery information. Please try again later.")))]
        return [("ABRP", no_evdata_resp(channel_id))]

    try:
        plan_resp = make_abrp_plan(
            car,
            [{"location": car_coordinate, "name": str(_("My Location"))}]+vehicle_route,
            min_highways
        )
        routes = plan_resp.get("routes") or []
        if len(routes) == 0:
            return [("ABRP", plan_error_resp(channel_id, _("ABRP could not plan a route. Please try again later.")))]

        preferred_route = min(routes, key=lambda d: d["score"])
        if "ARRIVAL_SOC_BELOW_ZERO" in preferred_route['legTags']:
            return [("ABRP", plan_error_resp(channel_id, _("Impossible plan to destination. There are not enough chargers along the route or your battery capacity is not enough. Proceed at your own risk.")))]


        start_dms = (0,0)
        abrp_waypoints = []
        for i, leg in enumerate(preferred_route["legs"][:7]): # 7 = 1 starting point, 1 destination, 5 waypoints
            origin = leg.get("origin") or {}
            if i == 0:
                start_dms = (origin.get("lat") or 0, origin.get("long") or 0)
                continue
            infobox = str(int(round((origin.get('arrivalSocFrac') or 0)*100, 0)))
            if "departureSocFrac" in origin and origin.get('departureSocFrac') != origin.get('arrivalSocFrac'):
                infobox += f"->{int(round((origin.get('departureSocFrac') or 0)*100, 0))}"
            infobox += "%"

            abrp_waypoints.append({
                "location": (origin.get("lat") or 0, origin.get("long") or 0),
                "name": f"{infobox} {origin.get('name')}",
                "type": "charger" if origin.get("type") == "ADDED_CHARGER" else "point"
            })


        points = [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8(abrp_waypoints[-1]["name"], limit=0x20),
                'dynamicDataField2': encode_utf8(abrp_waypoints[-1]["name"], limit=0x80),
                'dynamicDataField3': encode_utf8(abrp_waypoints[-1]["name"], limit=0x40),
                "DMSLocation": construct_dms_coordinate(abrp_waypoints[-1]["location"][0], abrp_waypoints[-1]["location"][1]),
                # is charging station flag?
                'flag2': 1,
                # waypoint number
                'flag3': 1,
                'dynamicField4': b'',
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                "bigDynamicField7": b'',
                "bigDynamicField8": b'',
                "iconField": 0x0001,
                "longField2": 0,
                "flag4": 0,
                "unknownLongId4": 0,
                "flag5": 0,
                "flag6": 0,
                "12byteField1": b'\x00' * 12,
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x80',
                "flag8": 0x80,
                "imageDataField": bytearray()
            }
        ]

        for i, point in enumerate(abrp_waypoints[:-1]):
            points.append(
                {
                    'itemId': i + 2,
                    'itemFlag1': i + 2,
                    'dynamicDataField1': encode_utf8(point["name"], limit=0x20),
                    'dynamicDataField2': encode_utf8(point["name"], limit=0x80),
                    'dynamicDataField3': encode_utf8(point["name"], limit=0x40),
                    "DMSLocation": construct_dms_coordinate(point["location"][0], point["location"][1]),
                    # is charging station flag?
                    'flag2': i + 2,
                    # waypoint number
                    'flag3': i + 2,
                    'dynamicField4': b'',
                    'dynamicField5': b'',
                    'dynamicField6': b'',
                    'unnamed_data': bytearray(),
                    "bigDynamicField7": b'',
                    "bigDynamicField8": b'',
                    "iconField": i + 2 if point["type"] == "point" else 0xf002,
                    "longField2": 0,
                    "flag4": 0,
                    "unknownLongId4": 0,
                    "flag5": 0,
                    "flag6": 0,
                    "12byteField1": b'\x00' * 12,
                    "12byteField2": b'\x00' * 12,
                    "mapPointFlag": b'\x80',
                    "flag8": 0x80,
                    "imageDataField": bytearray()
                }
            )

        resp_file = build_autodj_payload(
            0,
            channel_id,
            points,
            # start point
            {
                "type": 2,
                "data": construct_dms_coordinate(start_dms[0], start_dms[1]),
            },
            extra_fields={
                'stringField1': abrp_waypoints[-1]["name"],
                'stringField2': abrp_waypoints[-1]["name"],
                "mode0_processedFieldCntPos": len(points),
                "mode0_countOfSomeItems3": len(points),
                "countOfSomeItems": 1
            }
        )

        return [('ABRP', resp_file)]
    except Exception as e:
        logger.exception(e)
        return [("ABRP", plan_error_resp(channel_id, _("Failed to communicate with {brand}. Please try again later.", brand="ABRP"), _("Failed to communicate with {brand}. Please try again later.", brand="A Better Route Planner")))]