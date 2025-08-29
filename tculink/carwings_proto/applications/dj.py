import os
from datetime import datetime

from tculink.carwings_proto.databuffer import get_carwings_bininfo, construct_carwings_filepacket, compress_carwings
import xml.etree.ElementTree as ET

from tculink.carwings_proto.dataobjects import construct_chnmst_payload, construct_fvtchn_payload, \
    construct_send_to_car_channel
from tculink.carwings_proto.utils import get_cws_authenticated_car
from tculink.carwings_proto.xml import carwings_create_xmlfile_content
from unidecode import unidecode

# Demo folders and items
folders = [
    {
        'id': 0x85CF,
        'internal_id': 0x8080,
        'name1': 'Test folder 1',
        'name2': 'abc',
        'icon': 0x00,
        'flag': 0x01,
    },
    {
        'id': 0x85CD,
        'internal_id': 0x8081,
        'name1': 'Test folder 2',
        'name2': 'abc',
        'icon': 0x00,
        'flag': 0x02,
    }
]

channels = [
    {
        'id': 0x0000,
        'internal_id': 0x8080,
        'name1': 'Test 1',
        'name2': 'Item 2',
        'folder_id': 0x85CF,
        'icon': 0x0400,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0001,
        'internal_id': 0x8081,
        'name1': 'Test 2',
        'name2': 'Item 2',
        'folder_id': 0x85CF,
        'icon': 0x0002,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0002,
        'internal_id': 0x8082,
        'name1': 'Test 3',
        'name2': 'Item 3',
        'folder_id': 0x85CF,
        'icon': 0x0003,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0003,
        'internal_id': 0x8083,
        'name1': 'Test 3',
        'name2': 'Item 3',
        'folder_id': 0x85CF,
        'icon': 0x0004,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0004,
        'internal_id': 0x8084,
        'name1': 'Test 4',
        'name2': 'Item 4',
        'folder_id': 0x85CF,
        'icon': 0x0005,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0005,
        'internal_id': 0x8085,
        'name1': 'Test 5',
        'name2': 'Item 5',
        'folder_id': 0x85CF,
        'icon': 0x0006,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0006,
        'internal_id': 0x8085,
        'name1': 'Test 6',
        'name2': 'Item 6',
        'folder_id': 0x85CF,
        'icon': 0x0001,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x01
    },
    {
        'id': 0x0007,
        'internal_id': 0x8086,
        'name1': 'Test 7',
        'name2': 'Item 7',
        'folder_id': 0x85CF,
        'icon': 0x0100,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0008,
        'internal_id': 0x8087,
        'name1': 'Test 8',
        'name2': 'Item 8',
        'folder_id': 0x85CF,
        'icon': 0x0200,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0009,
        'internal_id': 0x8088,
        'name1': 'Test 9',
        'name2': 'Item 9',
        'folder_id': 0x85CF,
        'icon': 0x0310,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0010,
        'internal_id': 0x8089,
        'name1': 'Test 10',
        'name2': 'Item 10',
        'folder_id': 0x85CF,
        'icon': 0x0320,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0011,
        'internal_id': 0x808A,
        'name1': 'Test 11',
        'name2': 'Item 11',
        'folder_id': 0x85CF,
        'icon': 0x0330,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0012,
        'internal_id': 0x808B,
        'name1': 'Test 12',
        'name2': 'Item 12',
        'folder_id': 0x85CD,
        'icon': 0x0340,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0013,
        'internal_id': 0x808C,
        'name1': 'Test 13',
        'name2': 'Item 13',
        'folder_id': 0x85CD,
        'icon': 0x0350,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0014,
        'internal_id': 0x808D,
        'name1': 'Test 14',
        'name2': 'Item 14',
        'folder_id': 0x85CD,
        'icon': 0x0400,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0015,
        'internal_id': 0x808E,
        'name1': 'Test 15',
        'name2': 'Item 15',
        'folder_id': 0x85CD,
        'icon': 0x0600,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0016,
        'internal_id': 0x808F,
        'name1': 'Test 16',
        'name2': 'Item 16',
        'folder_id': 0x85CD,
        'icon': 0x0700,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0017,
        'internal_id': 0x8090,
        'name1': 'Test 17',
        'name2': 'Item 17',
        'folder_id': 0x85CD,
        'icon': 0x0800,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0018,
        'internal_id': 0x8090,
        'name1': 'Test 18',
        'name2': 'Item 18',
        'folder_id': 0x85CD,
        'icon': 0x0900,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0019,
        'internal_id': 0x8091,
        'name1': 'Test 19',
        'name2': 'Item 19',
        'folder_id': 0x85CD,
        'icon': 0x0a00,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0020,
        'internal_id': 0x8092,
        'name1': 'Test 20',
        'name2': 'Item 20',
        'folder_id': 0x85CD,
        'icon': 0x0b00,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    },
    {
        'id': 0x0021,
        'internal_id': 0x8093,
        'name1': 'Test 21',
        'name2': 'Item 21',
        'folder_id': 0x85CD,
        'icon': 0xFFFE,
        'enabled': True,
        'data1': bytearray(),
        'data2': bytearray(),
        'flag2': 0x00
    }
]


def handle_dj(xml_data, files):
    if 'send_data' in xml_data['service_info']['application']:
        if len(xml_data['service_info']['application']['send_data']) == 0:
            return None
        send_data = xml_data['service_info']['application']['send_data'][0]
        id_type = send_data['id_type']
        id_value = send_data['id']
        file_content = bytearray()
        if id_type == "file":
            # Retrieving file
            file_content = next((x for x in files if x['name'] == id_value), None)
            if file_content is None:
                print("File not found", id_value)
                return None
            file_content = file_content['content']

        # Parsing command from DJ payload
        dj_payload = get_carwings_bininfo(file_content)
        if dj_payload is None:
            print("DJ Payload is not valid!")
            log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                   datetime.now().strftime('%Y%m%d%H%M%S.%s'))
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, f"INVALID-{id_value}"), 'wb') as f:
                f.write(file_content)
            return None

        if len(dj_payload) < 2:
            print("DJ Payload is invalid!")
            log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                   datetime.now().strftime('%Y%m%d%H%M%S.%s'))
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, f"UNKNOWNDJPAYL-{id_value}"), 'wb') as f:
                f.write(file_content)
            return None

        action = dj_payload[1]

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})


        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "DJ"})

        if action == 0x01:
            print("Save to Favorite list func!")
        elif action == 0x00:
            print("Request func!")
            handler_id = (dj_payload[2] << 8) | (dj_payload[3])
            print("Handler ID", handler_id)
            # Request channel list (CHNLIST)
            if handler_id == 0x101:

                # Construct the message
                resp_file = construct_chnmst_payload(folders, channels)

                itms = [
                    {
                        'id': 0x0202,
                        'position': 1,
                        'channel_id': 0x0000,
                        'name1': 'Favourite 1',
                        'name2': 'Favt1',
                        'flag': 0x04
                    },
                    {
                        'id': 0x0201,
                        'position': 2,
                        'channel_id': 0x0000,
                        'name1': 'Favourite 2',
                        'name2': 'Favt2',
                        'flag': 0x04
                    }
                ]

                favt_file = construct_fvtchn_payload(itms)

                ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "CHANINF.001"})
                ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "FAVTINF.002"})

                op_inf = ET.SubElement(carwings_xml_root, "op_inf")
                ET.SubElement(op_inf, "timing", {"req": "normal"})

                xml_str = carwings_create_xmlfile_content(carwings_xml_root)
                files.append(("response.xml", xml_str.encode("utf-8"),))
                files.append(("CHANINF.001", resp_file))
                files.append(("FAVTINF.002", favt_file))

            # Request Channel Data (CHNDAT)
            elif handler_id == 0x102:
                if len(dj_payload) < 6:
                    print("Too short DJ payload for 0x102!")
                    return None
                chan_id = int.from_bytes([dj_payload[4], dj_payload[5]], byteorder='big')
                if chan_id == 0x000F:
                    print("Google SEND TO CAR!")
                    car_destinations = []
                    car = get_cws_authenticated_car(xml_data)
                    if car is not None:
                        if car.send_to_car_location is not None:
                            formatted_name = unidecode(car.send_to_car_location.name)
                            if formatted_name is None:
                                formatted_name = "Send to car destination"
                            if len(formatted_name) > 32:
                                formatted_name = formatted_name[:32]
                            car_destinations.append(
                                {
                                    "name": formatted_name,
                                    "name2": "jkl",
                                    "name3": "abc",
                                    "lat": car.send_to_car_location.lat,
                                    "lon": car.send_to_car_location.lon,
                                    "name4": "def",
                                    "name5": "ghi",
                                    "name6": "jkl",
                                    "name7": "mno",
                                    "name8": "pqr",
                                    "icon": 0x0001
                                }
                            )
                    resp_file = construct_send_to_car_channel(car_destinations)
                # Route planner has multiple channels: 0A, 0B, 0C, 0D, 0E.
                elif chan_id == 0x000A:
                    print("Route planner A")
                    # Send empty response for now until data format is figured out
                    resp_file = construct_send_to_car_channel([], channel_id=0x000A)
                else:
                    log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                           datetime.now().strftime('%Y%m%d%H%M%S.%s'))
                    os.makedirs(log_dir, exist_ok=True)
                    # Give generic empty list response for now
                    resp_file = bytearray.fromhex('00 00 00 00 00 00 00 00 00 01 02 01 FF FF 07 00'.replace(' ', ''))
                    resp_file[12] = dj_payload[4]
                    resp_file[13] = dj_payload[5]

                    with open(os.path.join(log_dir, f"UNKNOWNCHID-{id_value}"), 'wb') as f:
                        f.write(file_content)


                ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "CHANDAT.001"})

                op_inf = ET.SubElement(carwings_xml_root, "op_inf")
                ET.SubElement(op_inf, "timing", {"req": "normal"})

                xml_str = carwings_create_xmlfile_content(carwings_xml_root)
                files.append(("response.xml", xml_str.encode("utf-8"),))
                files.append(("CHANDAT.001", resp_file))
            else:
                log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                       datetime.now().strftime('%Y%m%d%H%M%S.%s'))
                os.makedirs(log_dir, exist_ok=True)
                with open(os.path.join(log_dir, f"UNKNOWNID-{id_value}"), 'wb') as f:
                    f.write(file_content)
        else:
            log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                   datetime.now().strftime('%Y%m%d%H%M%S.%s'))
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, f"UNKNOWNACT-{id_value}"), 'wb') as f:
                f.write(file_content)

        return compress_carwings(construct_carwings_filepacket(files))
    return None
