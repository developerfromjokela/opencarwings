import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime

from django.utils.translation import activate, get_language, deactivate

from tculink.carwings_proto.autodj.channels import get_info_channel_data
from tculink.carwings_proto.autodj.handler import handle_channel_response, handle_directory_response
from tculink.carwings_proto.databuffer import get_carwings_dj_payload, construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.dataobjects import construct_gnrlms_payload
from tculink.carwings_proto.utils import carwings_lang_to_code, get_cws_authenticated_car
from tculink.carwings_proto.xml import carwings_create_xmlfile_content
from django.utils.translation import gettext as _

logger = logging.getLogger("carwings_apl")


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
                logger.error("File not found, %s", id_value)
                return None
            file_content = file_content['content']

        # Parsing command from DJ payload
        dj_payload = get_carwings_dj_payload(file_content)
        if dj_payload is None:
            logger.error("DJ Payload is not valid!")
            log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                   datetime.now().strftime('%Y%m%d%H%M%S.%s'))
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, f"INVALID-{id_value}"), 'wb') as f:
                f.write(file_content)
            return None

        if len(dj_payload) < 2:
            logger.error("DJ Payload is invalid!")
            log_dir = os.path.join("logs", "dj", xml_data['authentication']['navi_id'],
                                   datetime.now().strftime('%Y%m%d%H%M%S.%s'))
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, f"UNKNOWNDJPAYL-{id_value}"), 'wb') as f:
                f.write(file_content)
            return None

        activate(carwings_lang_to_code(xml_data['base_info'].get('navigation_settings', {}).get('language', "uke")))

        logger.info("CWS lang: ")
        logger.info(get_language())

        count = dj_payload[0]

        action = dj_payload[1]
        command_list = dj_payload[2:]

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})


        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "DJ"})

        if action == 0x01:
            logger.info("Save to Favorite list func!")
            position = int.from_bytes(dj_payload[7:9], "big")
            channel_id = int.from_bytes(dj_payload[9:11], "big")
            car = get_cws_authenticated_car(xml_data)
            if car is None:
                resp_file = construct_gnrlms_payload(0xC, _("Not authenticated"), _("Please authenticate to Car Wings before saving a favorite channel"))
            else:
                channels, folders = get_info_channel_data(car)
                channel_info = next((c for c in channels if c['id'] == channel_id), None)
                if channel_info is None:
                    resp_file = construct_gnrlms_payload(0xC, _("Channel not found"), _("This channel does not exist and cannot be added to favorites list"))
                else:
                    car_favorites_map = car.favorite_channels
                    car_favorites_map[str(position)] = channel_info['id']
                    car.favorite_channels = car_favorites_map
                    car.save()
                    resp_file = construct_gnrlms_payload(0xB, _("Favorite channel added"), _("The channel has been added to favorites"))

            ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "CHANDAT.001"})

            op_inf = ET.SubElement(carwings_xml_root, "op_inf")
            ET.SubElement(op_inf, "timing", {"req": "normal"})

            xml_str = carwings_create_xmlfile_content(carwings_xml_root)
            files.append(("response.xml", xml_str.encode("utf-8"),))
            files.append(("CHANDAT.001", resp_file))
        elif action == 0x00:
            i = 0
            datapos = 0
            while i < count:
                if datapos > len(command_list) - 2:
                    break
                handler_id = (command_list[datapos] << 8) | (command_list[(datapos) + 1])
                i += 1
                logger.info("Handler ID: %s", hex(handler_id))
                if handler_id == 0x102:
                    channel_id = (command_list[datapos + 2] << 8) | (command_list[datapos + 3])
                    flag = command_list[datapos + 4]
                    logger.info("  ->Channel ID: %s", hex(channel_id))
                    logger.info("  ->Flag: %s", hex(flag))
                    for fidx, file in enumerate(handle_channel_response(xml_data, channel_id, app_elm)):
                        name = file[0]
                        name += f".{fidx+1}.{i+1:03}"
                        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": name})
                        files.append((name, file[1]))
                    datapos += 6
                elif handler_id == 0x101:
                    for fidx, file in enumerate(handle_directory_response(xml_data, app_elm)):
                        name = file[0]
                        name += f".{fidx+1}.{i+1:03}"
                        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": name})
                        files.append((name, file[1]))
                    datapos += 3
                else:
                    datapos += 3
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

        deactivate()

        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)

        files.insert(0, ("response.xml", xml_str.encode("utf-8"),))

        return compress_carwings(construct_carwings_filepacket(files))
    return None
