from django.utils.translation import gettext as _, activate, deactivate

from tculink.carwings_proto.autodj import NOT_FOUND_AUTODJ_ITEM, NOT_AUTHORIZED_AUTODJ_ITEM
from tculink.carwings_proto.autodj.channels import STANDARD_AUTODJ_CHANNELS, get_info_channel_data
from tculink.carwings_proto.dataobjects import construct_chnmst_payload, construct_fvtchn_payload, build_autodj_payload
from tculink.carwings_proto.utils import get_cws_authenticated_car, carwings_lang_to_code


def handle_directory_response(xml_data, returning_xml):

    activate(carwings_lang_to_code(xml_data['base_info'].get('navigation_settings', {}).get('language', "uke")))

    car = get_cws_authenticated_car(xml_data)
    channels, folders = get_info_channel_data(car)

    resp_file = construct_chnmst_payload(folders, channels)

    fav_channels = [
        {
            'id': 0xA000,
            'position': 1,
            'channel_id': 0x0000,
            'name1': str(_('Info from OpenCARWINGS')),
            'name2': str(_('Info from OpenCARWINGS')),
            'flag': 0x04
        }
    ]

    if car is not None:
        for pos, chan_id in car.favorite_channels.items():
            channel_info = next((x for x in channels if x['id'] == chan_id), None)
            if channel_info is not None:
                fav_channels.append({
                    'id': 40960+int(pos),
                    'position': int(pos),
                    'channel_id': chan_id,
                    'name1': channel_info['name1'],
                    'name2': channel_info['name2'],
                    'flag': 0x04
                })

    favt_file = construct_fvtchn_payload(fav_channels)

    deactivate()

    return [
        ("CHANINF", resp_file),
        ("FAVTINF", favt_file)
    ]

def handle_channel_response(xml_data, channel_id, returning_xml):
    car = get_cws_authenticated_car(xml_data)
    channels, folders = get_info_channel_data(car)

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
                'stringField1': _('Data Channel not available'),
                'stringField2': _('Data Channel not available'),
                "mode0_processedFieldCntPos": 1,
                "mode0_countOfSomeItems3": 1,
                "countOfSomeItems": 1
            }
        )
        return [('NOTFOUND', resp_file)]

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
                'stringField1': _('Not authorized'),
                'stringField2': _('Not authorized'),
                "mode0_processedFieldCntPos": 1,
                "mode0_countOfSomeItems3": 1,
                "countOfSomeItems": 1
            }
        )
        return [('NOTAUTH', resp_file)]

    return channel['processor'](xml_data, returning_xml, channel_id, car)