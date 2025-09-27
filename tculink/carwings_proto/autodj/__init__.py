from tculink.carwings_proto.utils import encode_utf8

# CARWINGS built-in icons
ICONS = {
    0x340: ("cloud.png", "cloud"),
    1: ("destination.png", "destination"),
    2: ("waypoint1.png", "waypoint1"),
    3: ("waypoint2.png", "waypoint2"),
    4: ("waypoint3.png", "waypoint3"),
    5: ("waypoint4.png", "waypoint4"),
    6: ("waypoint5.png", "waypoint5"),
    0x100: ("compasslink.png", "compasslink"),
    0x200: ("telephone.png", "telephone"),
    0x310: ("sun.png", "sun"),
    0x320: ("moon.png", "moon"),
    0x330: ("umbrella.png", "umbrella"),
    0x350: ("snowman.png", "snowman"),
    0x400: ("info.png", "info"),
    0x500: ("news.png", "news"),
    0x600: ("mail.png", "mail"),
    0x700: ("city.png", "city"),
    0x800: ("toll.png", "toll"),
    0x900: ("park.png", "park"),
    0xB00: ("explore.png", "explore"),
    0xFFFE: ("folder.png", "folder"),
}

NOT_FOUND_AUTODJ_ITEM = [
    {
        'itemId': 1,
        'itemFlag1': 1,
        'dynamicDataField1': encode_utf8('Data Channel not available'),
        'dynamicDataField2': b'',
        'dynamicDataField3': b'',
        "DMSLocation": b'\xFF' * 10,
        'flag2': 0,
        'flag3': 0,
        'dynamicField4': b'',
        'dynamicField5': b'',
        'dynamicField6': b'',
        'unnamed_data': bytearray(),
        "bigDynamicField7": encode_utf8('Data Channel not available'),
        "bigDynamicField8": encode_utf8('This Data Channel that was requested, is no longer available or accessible.'),
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

NOT_AVAIL_AUTODJ_ITEM = [
    {
        'itemId': 1,
        'itemFlag1': 1,
        'dynamicDataField1': encode_utf8('Data Channel not available'),
        'dynamicDataField2': b'',
        'dynamicDataField3': b'',
        "DMSLocation": b'\xFF' * 10,
        'flag2': 0,
        'flag3': 0,
        'dynamicField4': b'',
        'dynamicField5': b'',
        'dynamicField6': b'',
        'unnamed_data': bytearray(),
        "bigDynamicField7": encode_utf8('Data Channel not available'),
        "bigDynamicField8": encode_utf8('This Data Channel that was requested, is not available at the moment.'
                            ' Please try again later.'),
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

NOT_AUTHORIZED_AUTODJ_ITEM = [
    {
        'itemId': 1,
        'itemFlag1': 1,
        'dynamicDataField1': encode_utf8('Not authorized'),
        'dynamicDataField2': b'',
        'dynamicDataField3': b'',
        "DMSLocation": b'\xFF' * 10,
        'flag2': 0,
        'flag3': 0,
        'dynamicField4': b'',
        'dynamicField5': b'',
        'dynamicField6': b'',
        'unnamed_data': bytearray(),
        "bigDynamicField7": encode_utf8('Data Channel not available'),
        "bigDynamicField8": encode_utf8('To view this data channel, you will need to sign in with your Open Car Wings credentials. '
                            'Head to Car Wings settings and input your credentials under "Security settings".'),
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