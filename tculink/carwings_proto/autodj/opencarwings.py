import os
import xml.etree.ElementTree as ET

from tculink.carwings_proto.dataobjects import build_autodj_payload

RELEASE_NOTES = "What's new in OpenCARWINGS?\n1. Route Planner\n2.Multiple Send To Car Locations\n3. Data Channels\n4. Energy Information"

RELEASE_NOTES_SPK = ("What's new in Open CAR WINGS?\nNumber one. Route Planner. With new support of Route Planner, you can"
                     " plan your navigation routes in advance via your computer or mobile phone. It supports up to "
                     "5 waypoints and it is possible to send 5 routes to the car."
                     "\nNumber two. Multiple Send To Car Locations. Previously familar Google Send To Car function"
                     " supports sending up to six destinations, instead of previously supporting only one."
                     "\n3. Data Channels. Data channels are fully functional as of now and support for custom channels are coming soon."
                     "\n4. Energy Information. With the introduction of vehicle data, it is now possible to view your monthly trips, average consumption and more."
                     " Individual trips are transmitted to the Open Car Wings server with detailed information. In addition to this, data channels about E V information are now available.")

NOT_SIGNEDIN_NOTE = ("To make use of more functions of Open Car Wings, please sign in with your User I D and Car Wings "
                     "password inside your car.\n\nGo to Car Wings menu, Settings, Security Settings, to input and send "
                     "your credentials. Unlock even more useful functions and make your life easier with Open Car Wings.")

def get_infochannel(xml_data, returning_xml, channel_id, car):
    resources_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "images")
    with open(os.path.join(resources_dir, "releasenotes.jpg"), "rb") as f:
        releasenotes_img = f.read()
    response_chdata = [
        {
            'itemId': 1,
            'itemFlag1': 0x00,
            'dynamicDataField1': 'What\'s new?'.encode('utf-8'),
            'dynamicDataField2': f"What\'s new?".encode('utf-8'),
            'dynamicDataField3': b'',
            "DMSLocation": b'\xFF' * 10,
            'flag2': 0,
            'flag3': 0,
            'dynamicField4': b'',
            # phone num field
            'dynamicField5': b'',
            'dynamicField6': b'',
            'unnamed_data': bytearray(),
            # text shown on bottom
            "bigDynamicField7": RELEASE_NOTES.encode('utf-8'),
            "bigDynamicField8": RELEASE_NOTES_SPK.encode('utf-8'),
            "iconField": 0x400,
            # annoucnement sound, 1=yes,0=no
            "longField2": 1,
            "flag4": 1,
            "unknownLongId4": 0x0000,
            # feature flag? 0xa0 = dial, 0x0F = Img
            "flag5": 0x0F,
            "flag6": 0xBB,
            # image button title
            "12byteField1": b'\x00' * 12,
            # image name2
            "12byteField2": b'\x00' * 12,
            "mapPointFlag": b'\x20',
            # save flag
            "flag8": 0x00,
            "imageDataField": releasenotes_img,
        }
    ]

    if car is None:
        with open(os.path.join(resources_dir, "releasenotes.jpg"), "rb") as f:
            tips_img = f.read()
        response_chdata.append(
            {
                'itemId': 2,
                'itemFlag1': 0x00,
                'dynamicDataField1': 'Tips & Tricks'.encode('utf-8'),
                'dynamicDataField2': "Tips & Tricks".encode('utf-8'),
                'dynamicDataField3': b'',
                "DMSLocation": b'\xFF' * 10,
                'flag2': 0,
                'flag3': 0,
                'dynamicField4': b'',
                # phone num field
                'dynamicField5': b'',
                'dynamicField6': b'',
                'unnamed_data': bytearray(),
                # text shown on bottom
                "bigDynamicField7": NOT_SIGNEDIN_NOTE.encode('utf-8'),
                "bigDynamicField8": NOT_SIGNEDIN_NOTE.encode('utf-8'),
                "iconField": 0x400,
                # annoucnement sound, 1=yes,0=no
                "longField2": 1,
                "flag4": 1,
                "unknownLongId4": 0x0000,
                # feature flag? 0xa0 = dial, 0x0F = Img
                "flag5": 0x0F,
                "flag6": 0xBB,
                # image button title
                "12byteField1": b'\x00' * 12,
                # image name2
                "12byteField2": b'\x00' * 12,
                "mapPointFlag": b'\x20',
                # save flag
                "flag8": 0x00,
                "imageDataField": tips_img,
            }
        )

    resp_file = build_autodj_payload(
        0,
        channel_id,
        response_chdata,
        {
            "type": 6,
            "data": b'\x01'
        },
        extra_fields={
            'stringField1': 'Info from OpenCARWINGS'.encode('utf-8'),
            'stringField2': 'Info from OpenCARWINGS'.encode('utf-8'),
            "mode0_processedFieldCntPos": len(response_chdata),
            "mode0_countOfSomeItems3": len(response_chdata),
            "countOfSomeItems": 1
        }
    )

    ET.SubElement(returning_xml, "send_data", {"id_type": "file", "id": "INFOCHAN.001"})

    return [("INFOCHAN.001", resp_file)]