from django.utils.translation import gettext_lazy as _
from unidecode import unidecode

from tculink.carwings_proto.autodj import NOT_FOUND_AUTODJ_ITEM, NOT_AUTHORIZED_AUTODJ_ITEM
from tculink.carwings_proto.autodj.channels import STANDARD_AUTODJ_FOLDERS, STANDARD_AUTODJ_CHANNELS
from tculink.carwings_proto.dataobjects import construct_chnmst_payload, construct_fvtchn_payload, build_autodj_payload
from tculink.carwings_proto.utils import get_cws_authenticated_car


def handle_directory_response(xml_data, returning_xml):
    # TODO customisable user folder
    channels = [x for x in STANDARD_AUTODJ_CHANNELS if (x.get('internal', False) == False)]

    channels = [translate_chan_name(c) for c in channels]
    folders = [translate_chan_name(c) for c in STANDARD_AUTODJ_FOLDERS]

    resp_file = construct_chnmst_payload(folders, channels)

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

def translate_chan_name(chan):
    chan['name1'] = unidecode(_(chan['name1']))[:30]
    chan['name2'] = unidecode(_(chan['name2']))[:127]
    return chan

def handle_channel_response(xml_data, channel_id, returning_xml):
    channels = STANDARD_AUTODJ_CHANNELS
    # TODO if customisable channels add here

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