from tculink.carwings_proto.autodj import NOT_FOUND_AUTODJ_ITEM, NOT_AUTHORIZED_AUTODJ_ITEM
from tculink.carwings_proto.autodj.channels import STANDARD_AUTODJ_FOLDERS, STANDARD_AUTODJ_CHANNELS
from tculink.carwings_proto.dataobjects import construct_chnmst_payload, construct_fvtchn_payload, build_autodj_payload
import xml.etree.ElementTree as ET
from django.utils.translation import activate
from tculink.carwings_proto.utils import get_cws_authenticated_car, carwings_lang_to_code


def handle_directory_response(xml_data, returning_xml):
    # TODO customisable user folder
    channels = [x for x in STANDARD_AUTODJ_CHANNELS if (x.get('internal', False) == False)]
    resp_file = construct_chnmst_payload(STANDARD_AUTODJ_FOLDERS, channels)

    favt_file = construct_fvtchn_payload([
        {
            'id': 0xA001,
            'position': 1,
            'channel_id': 0x0000,
            'name1': 'Info from OpenCARWINGS',
            'name2': 'Info from OpenCARWINGS',
            'flag': 0x04
        }
    ])


    return [
        ("CHANINF", resp_file),
        ("FAVTINF", favt_file)
    ]


def handle_channel_response(xml_data, channel_id, returning_xml):
    # add exception for channel update channel (purpose?)
    #if channel_id == 0x270f:
    #    return []
    channels = STANDARD_AUTODJ_CHANNELS
    # TODO if customisable channels add here
    activate(carwings_lang_to_code(xml_data['base_info'].get('navigation_settings', {}).get('language', "uke")))

    channel = next((item for item in channels if item["id"] == channel_id), None)
    if channel is None or 'processor' not in channel:
        resp_file = build_autodj_payload(
            0,
            channel_id,
            NOT_FOUND_AUTODJ_ITEM,
            {
                "type": 6,
                "data": b'\x01'
            },
            extra_fields={
                'stringField1': 'Data Channel not available'.encode('utf-8'),
                'stringField2': 'Data Channel not available'.encode('utf-8'),
                "mode0_processedFieldCntPos": 1,
                "mode0_countOfSomeItems3": 1,
                "countOfSomeItems": 1
            }
        )
        return [('NOTFOUND', resp_file)]

    car = get_cws_authenticated_car(xml_data)
    if car is None and channel.get('auth', False) and not channel.get('internal', False):
        resp_file = build_autodj_payload(
            0,
            channel_id,
            NOT_AUTHORIZED_AUTODJ_ITEM,
            {
                "type": 6,
                "data": b'\x01'
            },
            extra_fields={
                'stringField1': 'Not authorized'.encode('utf-8'),
                'stringField2': 'Not authorized'.encode('utf-8'),
                "mode0_processedFieldCntPos": 1,
                "mode0_countOfSomeItems3": 1,
                "countOfSomeItems": 1
            }
        )
        return [('NOTAUTH', resp_file)]

    return channel['processor'](xml_data, returning_xml, channel_id, car)