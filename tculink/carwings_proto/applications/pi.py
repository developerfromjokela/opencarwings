import xml.etree.ElementTree as ET

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.xml import carwings_create_xmlfile_content


def handle_pi(xml_data, files):
    if 'send_data' in xml_data['service_info']['application']:
        send_data = xml_data['service_info']['application']['send_data']
        id_type = send_data['id_type']
        id_value = send_data['id']

        # Reserve file content for future, when protocol is reverse-engineered
        file_content = bytearray()
        if id_type == "file":
            file_content = next((x for x in files if x['name'] == id_value), None)
            if file_content is None:
                print("File not found", id_value)
                return None
            file_content = file_content['content']

        # Construct the payload (invalid, does nothing
        resp_file = bytes.fromhex('0583')

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})



        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "PI"})
        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "PIRESP.003"})


        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)
        files.append(("response.xml", xml_str.encode("utf-8"),))
        files.append(("PIRESP.003", resp_file,))

        return compress_carwings(construct_carwings_filepacket(files))
    return None