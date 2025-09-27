import geopy.distance
from django.utils.text import format_lazy
from django.utils.translation import gettext as _

from db.models import Car
from tculink.carwings_proto.dataobjects import build_autodj_payload, construct_dms_coordinate
from tculink.carwings_proto.utils import xml_coordinate_to_float, encode_utf8


def handle_send_to_car_adj(xml_data, returning_xml, channel_id, car: Car):
    car_destinations = []
    # TODO: up to 6 destinations
    for send_location in car.send_to_car_location.all().order_by('-created_at')[:6]:
        point_name = send_location.name
        if send_location.name is None:
            point_name = "Map Point"
        if len(point_name) > 32:
            point_name = point_name[:32]
        distance = 0
        if (xml_data.get('base_info', None) is not None
                and xml_data['base_info'].get('vehicle', None) is not None
                and xml_data['base_info']['vehicle'].get('coordinates', None) is not None):
            car_coordinate = xml_coordinate_to_float(xml_data['base_info']['vehicle']['coordinates'])
            distance = round(geopy.distance.geodesic(car_coordinate, (send_location.lat, send_location.lon)).km)
        car_destinations.append(
            {
                'itemId': send_location.id,
                'itemFlag1': 0x00,
                'dynamicDataField1': encode_utf8(point_name),
                'dynamicDataField2': b'',
                'dynamicDataField3': b'',
                "DMSLocation": construct_dms_coordinate(send_location.lat, send_location.lon),
                'flag2': 0x20,
                'flag3': 0x20,
                'dynamicField4': b'',
                # phone num field
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                # text shown on bottom
                "bigDynamicField7": encode_utf8(point_name),
                "bigDynamicField8": encode_utf8(format_lazy(_('Location point, "{point_name}", which is {distance} kilometers away. '
                                    f'Set it as destination by pressing pause and setting map point as destination.'),
                                                    point_name=point_name, distance=distance)),
                "iconField": 0x0001,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 1,
                "unknownLongId4": 0x0000,
                # feature flag? 0xa0 = dial, 0x0F = Img
                "flag5": 0x80,
                "flag6": 0x00,
                # image button title
                "12byteField1": b'\x00' * 12,
                # image name2
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                "flag8": 0,
                "imageDataField": bytearray()
            }
        )


    if len(car_destinations) == 0:
        car_destinations = [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8('Google Send To Car'),
                'dynamicDataField2': b'',
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                "bigDynamicField7": encode_utf8(_('Google Send To Car: No Destinations')),
                "bigDynamicField8": encode_utf8(_('There are no destinations sent to the car. '
                                    'Please send at least one destination from your computer or mobile device and'
                                    ' access this channel again.')),
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
        ]
    resp_file = build_autodj_payload(
        0,
        channel_id,
        car_destinations,
        {
            "type": 6,
            "data": b'\x01'
        },
        extra_fields={
            'stringField1': 'Google Send to Car',
            'stringField2': 'Google Send to Car',
            "mode0_processedFieldCntPos": len(car_destinations),
            "mode0_countOfSomeItems3": len(car_destinations),
            "countOfSomeItems": 1
        }
    )

    return [("SENDTOCAR.adj", resp_file)]

def handle_send_to_car(_, returning_xml, channel_id, car: Car):
    car_destinations = []
    if car is not None:
        for send_location in car.send_to_car_location.all().order_by('-created_at')[:6]:
            point_name = send_location.name
            if send_location.name is None:
                point_name = "Map Point"
            if len(point_name) > 32:
                point_name = point_name[:32]
            car_destinations.append(
                {
                    'itemId': 0,
                    'itemFlag1': 0,
                    'dynamicDataField1': encode_utf8(point_name),
                    'dynamicDataField2': [],
                    'dynamicDataField3': [],
                    "DMSLocation": construct_dms_coordinate(send_location.lat, send_location.lon),
                    'flag2': 1,
                    'flag3': 1,
                    'dynamicField4': [],
                    'dynamicField5': [],
                    'dynamicField6': [],
                    'unnamed_data': bytearray(),
                    "bigDynamicField7": [],
                    "bigDynamicField8": [],
                    "iconField": 0x0001,
                    "longField2": 0,
                    "flag4": 0,
                    "unknownLongId4": 0,
                    "flag5": 0x80,
                    "flag6": 0,
                    "12byteField1": b'\x00' * 12,
                    "12byteField2": b'\x00' * 12,
                    "mapPointFlag": b'\x00',
                    "flag8": 0,
                    "imageDataField": bytearray()
                }
            )

    resp_file = build_autodj_payload(
        1,
        channel_id,
        car_destinations,
        # start point!
        {
            "type": 6,
            "data": b'\x00',
        },
    )

    return [("SENDTOCAR", resp_file)]