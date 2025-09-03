import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime

from tculink.carwings_proto.autodj.handler import handle_channel_response, handle_directory_response
from tculink.carwings_proto.databuffer import get_carwings_bininfo, construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.xml import carwings_create_xmlfile_content

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
        dj_payload = get_carwings_bininfo(file_content)
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

        action = dj_payload[1]

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})


        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "DJ"})

        if action == 0x01:
            logger.info("Save to Favorite list func!")
            resp_file = bytearray.fromhex('00 00 00 00 00 00 00 00 00 04 02 0C 13 4E 6F 74 20 69 6D 70 6C 65 6D 65 6E 74 65 64 20 79 65 74 31 53 61 76 69 6E 67 20 74 6F 20 66 61 76 6F 72 69 74 65 73 20 6C 69 73 74 20 69 73 20 6E 6F 74 20 77 6F 72 6B 69 6E 67 20 63 75 72 72 65 6E 74 6C 79')
            print(resp_file.hex())
            ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "CHANDAT.001"})

            op_inf = ET.SubElement(carwings_xml_root, "op_inf")
            ET.SubElement(op_inf, "timing", {"req": "normal"})

            xml_str = carwings_create_xmlfile_content(carwings_xml_root)
            print(xml_str)
            files.append(("response.xml", xml_str.encode("utf-8"),))
            files.append(("CHANDAT.001", resp_file))
        elif action == 0x00:
            logger.info("Request func!")
            handler_id = (dj_payload[2] << 8) | (dj_payload[3])
            logger.info("Handler ID, %d", handler_id)
            # Request channel list (CHNLIST)
            if handler_id == 0x101:
                for file in handle_directory_response(xml_data, app_elm):
                    files.append(file)

                op_inf = ET.SubElement(carwings_xml_root, "op_inf")
                ET.SubElement(op_inf, "timing", {"req": "normal"})

                xml_str = carwings_create_xmlfile_content(carwings_xml_root)
                files.insert(0 , ("response.xml", xml_str.encode("utf-8"),))
            # Request Channel Data (CHNDAT)
            elif handler_id == 0x102:
                if len(dj_payload) < 6:
                    logger.error("Too short DJ payload for 0x102!")
                    return None
                chan_id = int.from_bytes([dj_payload[4], dj_payload[5]], byteorder='big')
                for file in handle_channel_response(xml_data, chan_id, app_elm):
                    files.append(file)

                op_inf = ET.SubElement(carwings_xml_root, "op_inf")
                ET.SubElement(op_inf, "timing", {"req": "normal"})

                xml_str = carwings_create_xmlfile_content(carwings_xml_root)
                files.insert(0, ("response.xml", xml_str.encode("utf-8"),))
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
