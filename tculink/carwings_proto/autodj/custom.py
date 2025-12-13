import base64
import logging
import requests
from django.conf import settings
from rest_framework import serializers
from db.models import Car
from tculink.carwings_proto.autodj import NOT_AVAIL_AUTODJ_ITEM
from tculink.carwings_proto.dataobjects import build_autodj_payload, construct_dms_coordinate
from tculink.carwings_proto.utils import carwings_lang_to_code, xml_coordinate_to_float, encode_utf8

logger = logging.getLogger("carwings_apl")

class ChannelMapPoint(serializers.Serializer):
    lat = serializers.FloatField()
    lon = serializers.FloatField()

class ChannelData(serializers.Serializer):
    title1 = serializers.CharField(max_length=0x20)
    title2 = serializers.CharField(max_length=0x80)
    title3 = serializers.CharField(max_length=0x40, required=False, allow_blank=True)
    onscreen = serializers.CharField(max_length=0x400, required=False, allow_blank=True)
    tts = serializers.CharField(max_length=0x400, required=False, allow_blank=True)
    map_point = ChannelMapPoint(required=False)
    phone_number = serializers.CharField(max_length=0x20, required=False, allow_blank=True)
    img_base64 = serializers.CharField(max_length=25000, required=False, allow_blank=True)
    bell = serializers.BooleanField(default=True, required=False)
    save = serializers.BooleanField(default=True, required=False)


def handle_custom_channel(xml_data, _, channel_id, car: Car):
    custom_chan_num = channel_id - 0x1000
    chan_info = car.custom_channels[str(custom_chan_num)]

    response_chdata = NOT_AVAIL_AUTODJ_ITEM

    send_payload = {
        'lang': carwings_lang_to_code(xml_data['base_info'].get('navigation_settings', {}).get('language', "uke")),
        'tz': xml_data['base_info'].get('navigation_settings', {}).get('time_zone', "+0.00"),
        'distance_unit': xml_data['base_info'].get('navigation_settings', {}).get('distance_display', "km"),
        'temp_unit': xml_data['base_info'].get('navigation_settings', {}).get('temperature_display', "C"),
    }

    if chan_info.get('location', False):
        try:
            location_info = xml_coordinate_to_float(xml_data['base_info'].get('vehicle', {}).get('coordinates', {}))
        except:
            location_info = (None, None)
        send_payload['lat'] = location_info[0]
        send_payload['lon'] = location_info[1]
        send_payload['speed'] = xml_data['base_info'].get('vehicle', {}).get('speed', "err")
        send_payload['direction'] = xml_data['base_info'].get('vehicle', {}).get('direction', "err")
        send_payload['car_status'] = xml_data['base_info'].get('vehicle', {}).get('status', "err")

    logger.debug("send_payload: %s", send_payload)

    proxy_settings = {}
    if hasattr(settings, 'USER_CONTENT_PROXY'):
        proxy_settings = settings.USER_CONTENT_PROXY

    try:
        chn_data = requests.post(chan_info['url'], json=send_payload, timeout=10, proxies=proxy_settings,
                                 headers={
                                     'content-type': 'application/json',
                                     'user-agent': 'OpenCARWINGS/1.0',
                                     'accept-language': send_payload['lang']
                                 })
        chn_data = chn_data.json()
        validated_chndata = ChannelData(data=chn_data[:2], many=True)
        if validated_chndata.is_valid(raise_exception=False):
            custom_chdata = []
            for idx, itm in enumerate(validated_chndata.validated_data):
                feature_flag = 0x90
                feature_flag2 = 0xBB
                try:
                    img_buffer = base64.b64decode(itm['img_base64'])
                    if len(img_buffer) > 15480:
                        img_buffer = bytes()
                except:
                    img_buffer = bytes()
                if len(itm.get('phone_number', '')) > 0:
                    feature_flag += 0x10

                if len(img_buffer) > 0:
                    feature_flag += 0x0F

                custom_chdata.append({
                        'itemId': idx+1,
                        'itemFlag1': 0x00,
                        'dynamicDataField1': encode_utf8(itm.get('title1', ''), limit=0x20),
                        'dynamicDataField2': encode_utf8(itm.get('title2', ''), limit=0x80),
                        'dynamicDataField3': encode_utf8(itm.get('title3', ''), limit=0x40),
                        "DMSLocation": construct_dms_coordinate(itm["map_point"]["lat"], itm["map_point"]["lon"]) if "map_point" in itm and itm["map_point"] else b'\xFF' * 10,
                        'flag2': 0,
                        'flag3': 0,
                        'dynamicField4': b'',
                        # phone num field
                        'dynamicField5': encode_utf8(itm.get('phone_number', ''), limit=0x20),
                        'dynamicField6': b'',
                        'unnamed_data': bytearray(),
                        # text shown on bottom
                        "bigDynamicField7": encode_utf8(itm.get('onscreen', ''), limit=0x400),
                        "bigDynamicField8": encode_utf8(itm.get('tts', ''), limit=0x400),
                        "iconField": 0x0400,
                        # annoucnement sound, 1=yes,0=no
                        "longField2": 1 if itm.get('bell', True) else 0,
                        "flag4": 1,
                        "unknownLongId4": 0x0000,
                        # feature flag? 0xa0 = dial, 0x0F = Img
                        "flag5": feature_flag,
                        "flag6": feature_flag2,
                        # image button title
                        "12byteField1": b'\x00' * 12,
                        # image name2
                        "12byteField2": b'\x00' * 12,
                        "mapPointFlag": b'\x20',
                        # save flag
                        "flag8": 0x80 if itm.get('save', False) else 0,
                        "imageDataField": img_buffer,
                    })

            if len(custom_chdata) > 0:
                response_chdata = custom_chdata

    except Exception as e:
        logger.exception(e)

    resp_file = build_autodj_payload(
        0,
        channel_id,
        response_chdata,
        {
            "type": 6,
            "data": b''
        },
        extra_fields={
            'stringField1': chan_info['name'],
            'stringField2': chan_info['name'],
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )

    return [("CUSTOM", resp_file)]
