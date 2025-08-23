import xml.etree.ElementTree as ET
from xml.dom import minidom

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.xml import carwings_create_xmlfile_content


def handle_gls(xml_data, files):
    if 'send_data' in xml_data['service_info']['application']:
        send_data = xml_data['service_info']['application']['send_data']
        id_type = send_data['id_type']
        id_value = send_data['id']
        file_content = bytearray()
        if id_type == "file":
            print("Retrieving file", id_value)
            file_content = next((x for x in files if x['name'] == id_value), None)
            if file_content is None:
                print("File not found", id_value)
                return None
            print("File content", file_content['content'].hex())
            file_content = file_content['content']

        print("GLS Command", file_content)

        print("Sending List")

        # Construct the payload
        resp_file = bytes.fromhex('00 00 00 00 00 00 00 00 00 03 01'.replace(' ', ''))

        #resptype
        resp_file += bytes.fromhex('02')

        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Results estresults="1" start="0" end="1">\n'
               '<LegalNotice>aa</LegalNotice>\n'
               '<Listings><Listing>\n'
               '<Location>\n'
               '<long>139.6917</long>\n'
               '<lat>35.6895</lat>\n'
               '</Location>\n'
               '<Name>Sample Place</Name>\n'
               '<Addr>123 Main St</Addr>\n'
               '<City>Tokyo</City>\n'
               '<Region>Kanto</Region>\n'
               '<Phone>123-456-7890</Phone>\n'
               '<Reviews>\n'
               '<starRating>4.5</starRating>\n'
               '</Reviews>\n'
               '<LatLng>35.6895,139.6917</LatLng>\n'
               '<ClickTrackingUrl>https://example.com/track</ClickTrackingUrl>\n'
               '<Distance>\n'
               '<DisplayValue>5.2</DisplayValue>\n'
               '<Units>km</Units>\n'
               '</Distance>\n'
               '</Listing></Listings>\n'
               '</Results>').encode('utf-8')

        reparsed = minidom.parseString(xml)
        pretty_xml = reparsed.toprettyxml(indent="")

        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        google_xml = (xml_declaration + pretty_xml).encode('utf-8')
        resp_file += len(google_xml).to_bytes(4, byteorder='big')
        resp_file += google_xml

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})



        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "GLS"})
        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "GLSRESP.002"})


        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)
        files.append(("response.xml", xml_str.encode("utf-8"),))
        files.append(("GLSRESP.002", resp_file,))

        return compress_carwings(construct_carwings_filepacket(files))


    return None