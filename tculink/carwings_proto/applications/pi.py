import os
import xml.etree.ElementTree as ET
from datetime import datetime
import random

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings, probe_xor_data
from tculink.carwings_proto.xml import carwings_create_xmlfile_content


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
                print("File not found", id_value)
                return None
            file_content = file_content['content']


            command_id = int.from_bytes([file_content[4], file_content[5]], byteorder="big")

            if command_id == 0x583:
                print("0x583 Init!")
                print("0x583 Version1: ", hex(file_content[6]))
                print("0x583 Version2: ", hex(file_content[7]))

                # Send request to start sending over data
                # 010f 01, 0x0583
                outgoing_files.append(("PIRESP1.003", bytes.fromhex('00 00 00 00 00 00 00 00 00 01 0f 01')))
                outgoing_files.append(("PIRESP2.003", bytes.fromhex('00 00 00 00 00 00 00 00 00 04 01 05 83')))

                filenames.append("PIRESP1.003")
                filenames.append("PIRESP2.003")
            elif command_id == 0x581:
                print("0x581 Incoming Data")
                filename_length = int(file_content[6])
                filename_offset = 7+filename_length
                filename = file_content[7:filename_offset].decode('utf-8')
                if len(filename) > 128:
                    filename = filename[:128]
                print("0x581 Filename LEN: ", filename_length)
                print("0x581 Filename: ", filename)

                print("Retrieving file", filename)
                probe_data = next((x for x in files if x['name'] == filename), None)
                if probe_data is None:
                    print("Probe File not found", filename)
                    return None

                probe_data = probe_data["content"]

                if probe_data[0] == 0x05 and probe_data[1] == 0x81:
                    if len(probe_data) < 10:
                        print("Probe File too small", filename)
                    else:
                        data_length = int.from_bytes([probe_data[3], probe_data[4], probe_data[5]], byteorder="big")-8
                        xor_key = probe_data[6]
                        file_number = int.from_bytes([probe_data[7], probe_data[8]], byteorder="big")
                        coordinate_system = probe_data[9]

                        print("Probe file metadata:")
                        print("  DataLength: ", data_length)
                        print("  FileNumber: ", file_number)
                        print("  XORKey: ", hex(xor_key))
                        print("  CoordinateSystem: ", hex(coordinate_system))

                        decrypted_data = bytearray(probe_data[:10])
                        decrypted_data += probe_xor_data(probe_data[10:], xor_key)

                        file_path = os.path.join(log_dir,filename)

                        if os.path.exists(file_path):
                            file_path = os.path.join(log_dir, f"dupl-{random.randrange(111111, 999999, 6)}-{filename}")

                        with open(file_path, 'wb') as f:
                            f.write(decrypted_data)

                        confirmation_content = bytearray.fromhex('00 00 00 00 00 00 00 00 00 05 14')
                        confirmation_content += file_number.to_bytes(2, byteorder="big")

                        outgoing_files.append((f"PICONFIRM{file_number}.003", confirmation_content))
                        filenames.append(f"PICONFIRM{file_number}.003")
                else:
                    print("Invalid Probe file signature! Got: "+hex(probe_data[0])+hex(probe_data[1]))
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

        return compress_carwings(construct_carwings_filepacket(files))
    return None