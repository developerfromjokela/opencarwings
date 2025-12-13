from db.models import Car
from tculink.carwings_proto.dataobjects import build_autodj_payload, construct_dms_coordinate

from django.utils.translation import gettext as _
from django.utils.text import format_lazy

from tculink.carwings_proto.utils import encode_utf8


def handle_routeplanner(unused, returning_xml, channel_id, car: Car, page):
    # routeplans, 1,2,3,4,5
    routeplan_num = channel_id - 0x0009
    car_destinations = []
    route_plans = car.route_plans.all()
    if len(route_plans) < routeplan_num:
        resp_file = build_autodj_payload(
            0,
            channel_id,
            [
                {
                    'itemId': 1,
                    'itemFlag1': 1,
                    'dynamicDataField1': encode_utf8(_('Route Plan not available')),
                    'dynamicDataField2': b'',
                    'dynamicDataField3': b'',
                    "DMSLocation": b'\xFF' * 10,
                    'flag2': 0,
                    'flag3': 0,
                    'dynamicField4': b'',
                    'dynamicField5': b'',
                    'dynamicField6': b'',
                    'unnamed_data': bytearray(),
                    "bigDynamicField7": encode_utf8(_('Route Plan not available')),
                    "bigDynamicField8": encode_utf8(_('This route plan is empty. Please save a route plan online and try again.')),
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
            # start point!
            {
                "type": 6,
                "data": b'\x01',
            },
            extra_fields={
                'stringField1': format_lazy(_('Route Plan {num}'), num=routeplan_num),
                'stringField2': format_lazy(_('Route Plan {num}'), num=routeplan_num),
                "mode0_processedFieldCntPos": 1,
                "mode0_countOfSomeItems3": 1,
                "countOfSomeItems": 1
            }
        )
    else:
        route_plan = route_plans[routeplan_num-1]
        plan_name = route_plan.name
        if len(plan_name) > 31:
            plan_name = plan_name[:31]
        # finish
        points = [
            {
                'itemId': 1,
                'itemFlag1': 1,
                'dynamicDataField1': encode_utf8(route_plan.finish_name, limit=0x20),
                'dynamicDataField2': encode_utf8(route_plan.finish_name, limit=0x80),
                'dynamicDataField3': encode_utf8(route_plan.finish_name, limit=0x40),
                "DMSLocation": construct_dms_coordinate(route_plan.finish_lat, route_plan.finish_lon),
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
                "flag8": 0,
                "imageDataField": bytearray()
            }
        ]
        for wp in range(1, 5+1):
            if getattr(route_plan, f"point{wp}_name", None) and getattr(route_plan, f"point{wp}_lat", None) and getattr(route_plan, f"point{wp}_lon", None):
                point_name = getattr(route_plan, f"point{wp}_name")
                if len(point_name) > 31:
                    point_name = plan_name[:31]
                points.append(
                    {
                        'itemId': wp+1,
                        'itemFlag1': wp+1,
                        'dynamicDataField1': encode_utf8(point_name, limit=0x20),
                        'dynamicDataField2': encode_utf8(point_name, limit=0x80),
                        'dynamicDataField3': encode_utf8(point_name, limit=0x40),
                        "DMSLocation": construct_dms_coordinate(getattr(route_plan, f"point{wp}_lat", None), getattr(route_plan, f"point{wp}_lon", None)),
                        # is charging station flag?
                        'flag2': wp+1,
                        # waypoint number
                        'flag3': wp+1,
                        'dynamicField4': b'',
                        'dynamicField5': b'',
                        'dynamicField6': b'',
                        'unnamed_data': bytearray(),
                        "bigDynamicField7": b'',
                        "bigDynamicField8": b'',
                        "iconField": wp+1,
                        "longField2": 0,
                        "flag4": 0,
                        "unknownLongId4": 0,
                        "flag5": 0,
                        "flag6": 0,
                        "12byteField1": b'\x00' * 12,
                        "12byteField2": b'\x00' * 12,
                        "mapPointFlag": b'\x80',
                        "flag8": 0,
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
                "data": construct_dms_coordinate(route_plan.start_lat, route_plan.start_lon),
            },
            extra_fields={
                'stringField1': plan_name,
                'stringField2': plan_name,
                "mode0_processedFieldCntPos": len(points),
                "mode0_countOfSomeItems3": len(points),
                "countOfSomeItems": 1
            }
        )

    return [(f"ROUTEPLAN{routeplan_num}", resp_file)]