import xml.etree.ElementTree as ET

from db.models import Car
from tculink.carwings_proto.dataobjects import build_autodj_payload


def handle_routeplanner(_, returning_xml, channel_id, car: Car):
    # routeplans, 1,2,3,4,5
    routeplan_num = channel_id - 0x0009
    car_destinations = []
    # TODO: implement routeplans

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
    ET.SubElement(returning_xml, "send_data", {"id_type": "file", "id": "SENDTOCAR.001"})

    return [("SENDTOCAR.001", resp_file)]