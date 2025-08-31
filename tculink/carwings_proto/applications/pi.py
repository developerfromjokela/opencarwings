import os
import xml.etree.ElementTree as ET
from datetime import datetime
import random

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings, probe_xor_data
from tculink.carwings_proto.probe_crm import parse_crmfile, update_crm_to_db
from tculink.carwings_proto.utils import calculate_prb_data_checksum, get_cws_authenticated_car
from tculink.carwings_proto.xml import carwings_create_xmlfile_content
import logging
logger = logging.getLogger("probe")

def handle_pi(xml_data, files):
    if 'send_data' in xml_data['service_info']['application']:
        outgoing_files = []

        filenames = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})

        log_dir = os.path.join("logs", "probe", xml_data['authentication']['navi_id'], datetime.now().strftime('%Y%m%d%H%M'))
        os.makedirs(log_dir, exist_ok=True)

        for send_data in xml_data['service_info']['application']['send_data']:
            id_type = send_data['id_type']
            id_value = send_data['id']
            if id_type != "file":
                return None
            file_content = next((x for x in files if x['name'] == id_value), None)
            if file_content is None:
                logger.error("File not found: %s", id_value)
                return None
            file_content = file_content['content']


            command_id = int.from_bytes([file_content[4], file_content[5]], byteorder="big")

            if command_id == 0x583:
                logger.info("0x583 Init!")
                logger.info("0x583 Version1: %s", hex(file_content[6]))
                logger.info("0x583 Version2: %s", hex(file_content[7]))

                # Send request to start sending over data
                # 010f 01, 0x0583
                outgoing_files.append(("PIRESP1.003", bytes.fromhex('00 00 00 00 00 00 00 00 00 01 0f 01')))
                outgoing_files.append(("PIRESP2.003", bytes.fromhex('00 00 00 00 00 00 00 00 00 04 01 05 83')))

                filenames.append("PIRESP1.003")
                filenames.append("PIRESP2.003")
            elif command_id == 0x581:
                logger.info("0x581 Incoming Data")
                filename_length = int(file_content[6])
                filename_offset = 7+filename_length
                filename = file_content[7:filename_offset].decode('utf-8')
                if len(filename) > 128:
                    filename = filename[:128]
                logger.info("0x581 Filename LEN: %d", filename_length)
                logger.info("0x581 Filename: %s", filename)

                logger.info("Retrieving file %s", filename)
                probe_data = next((x for x in files if x['name'] == filename), None)
                if probe_data is None:
                    logger.error("Probe File not found, %s", filename)
                    return None

                probe_data = probe_data["content"]


                if probe_data[0] == 0x05 and probe_data[1] == 0x81:
                    if len(probe_data) < 10:
                        logger.info("Probe File too small, %s", filename)
                    else:
                        data_length = int.from_bytes([probe_data[3], probe_data[4], probe_data[5]], byteorder="big")-8
                        xor_key = probe_data[6]
                        file_number = int.from_bytes([probe_data[7], probe_data[8]], byteorder="big")
                        coordinate_system = probe_data[9]
                        checksum_byte = probe_data[-1]

                        logger.info("Probe file metadata:")
                        logger.info("  DataLength: %d", data_length)
                        logger.info("  FileNumber: %d", file_number)
                        logger.info("  XORKey: %s", hex(xor_key))
                        logger.info("  Checksum: %s", hex(checksum_byte))
                        logger.info("  CoordinateSystem: %s", hex(coordinate_system))

                        checksum = calculate_prb_data_checksum(probe_data[2:], len(probe_data) - 2)
                        if checksum != checksum_byte:
                            logger.info("Probe file checksum error!")
                            file_path = os.path.join(log_dir, f"CHKSUMERR-{hex(checksum_byte)}-{hex(checksum)}-{filename}")
                            if os.path.exists(file_path):
                                file_path = os.path.join(log_dir,
                                                         f"dupl-{random.randrange(111111, 999999, 6)}-CHKSUMERR-{hex(checksum_byte)}-{hex(checksum)}-{filename}")
                            with open(file_path, 'wb') as f:
                                f.write(probe_data)
                        else:
                            decrypted_data = bytearray(probe_data[:10])
                            decrypted_data += probe_xor_data(probe_data[10:], xor_key)

                            file_path = os.path.join(log_dir,filename)

                            if os.path.exists(file_path):
                                file_path = os.path.join(log_dir, f"dupl-{random.randrange(111111, 999999, 6)}-{filename}")

                            with open(file_path, 'wb') as f:
                                f.write(decrypted_data)

                            if len(decrypted_data) > 38:
                                data = decrypted_data[38:]
                                if data[0] == 0xE1:
                                    logger.info("CRM File!")
                                    car_ref = get_cws_authenticated_car(xml_data)
                                    if car_ref is not None:
                                        try:
                                            crm_data = parse_crmfile(decrypted_data)
                                            update_crm_to_db(car_ref, crm_data)
                                        except Exception as e:
                                            logger.error("CRMFILE ERR")
                                            logger.exception(e)
                                elif data[0] == 0x05:
                                    logger.info("DOT file!")
                                    # TODO dotfile handling, implement when format known


                            confirmation_content = bytearray.fromhex('00 00 00 00 00 00 00 00 00 05 14')
                            confirmation_content += file_number.to_bytes(2, byteorder="big")

                            outgoing_files.append((f"PICONFIRM{file_number}.003", confirmation_content))
                            filenames.append(f"PICONFIRM{file_number}.003")
                else:
                    logger.error("Invalid Probe file signature! Got: %s,%s", hex(probe_data[0]), hex(probe_data[1]))
                    file_path = os.path.join(log_dir, f"UNKNOWN-{filename}")

                    if os.path.exists(file_path):
                        file_path = os.path.join(log_dir, f"dupl-{random.randrange(111111, 999999, 6)}-UNKNOWN-{filename}")

                    with open(file_path, 'wb') as f:
                        f.write(probe_data)
            else:
                # Unknown request, write to log
                file_path = os.path.join(log_dir, id_value)

                if os.path.exists(file_path):
                    file_path = os.path.join(log_dir, f"dupl-{random.randrange(111111, 999999, 6)}-{id_value}")

                with open(file_path, 'wb') as f:
                    f.write(file_content)


        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "PI"})

        for filename in filenames:
            ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": filename})


        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)
        outgoing_files.insert(0, ("response.xml", xml_str.encode("utf-8"),))

        return compress_carwings(construct_carwings_filepacket(outgoing_files))
    return None