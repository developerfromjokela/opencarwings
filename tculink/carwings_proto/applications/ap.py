import xml.etree.ElementTree as ET

from db.models import Car
from tculink.carwings_proto.databuffer import compress_carwings, construct_carwings_filepacket
from tculink.carwings_proto.xml import carwings_create_xmlfile_content


def handle_ap(xml_data, _):
    if 'authentication' in xml_data:

        auth_result = True
        reason_title = None
        reason_desc = None

        car_vin = xml_data['authentication']['vin']
        dcm_id = xml_data['authentication']['dcm_id']
        sim_id = xml_data['authentication']['sim_id']

        username = xml_data['authentication']['user_id']
        password = xml_data['authentication']['password']
        # find car
        try:
            car = Car.objects.get(vin=car_vin)
            if car is None:
                auth_result = False
                reason_title = 'Car not registered with OpenCARWINGS'
                reason_desc = 'The car has not been registered with Open Carwings. Visit Open Carwings website to register your vehicle.'

            # confirm TCU ID
            if auth_result and dcm_id != car.tcu_serial:
                auth_result = False
                reason_title = 'TCU ID mismatch'
                reason_desc = ('The TCU ID is incorrect. Please correct your TCU ID by visiting '
                               'Open Carwings portal. You can find the ID under Menu, Carwings, '
                               'Carwings settings and press Unit ID Information.')

            # confirm SIM ID
            if auth_result and car.iccid != sim_id:
                auth_result = False
                reason_title = 'Sim ID Mismatch'
                reason_desc = ('The SIM ID is incorrect. Please correct your SIM ID by visiting '
                               'Open Carwings portal. You can find the ID under Menu, Carwings, '
                               'Carwings settings and press Unit ID Information.')

            # confirm user&pass
            if auth_result and car.owner.username != username or car.owner.tcu_pass_hash != password:
                auth_result = False
                reason_title = 'Username or Password is incorrect.'
                reason_desc = ('The username or password is incorrect. '
                               'Please correct your username or password and try again.')
        except Car.DoesNotExist:
            auth_result = False
            reason_title = 'Car not registered with OpenCARWINGS'
            reason_desc = 'The car has not been registered with Open Carwings. Visit Open Carwings website to register your vehicle.'

        files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        aut_inf = ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok" if auth_result else "ng"})
        if reason_title is not None and reason_desc is not None:
            ET.SubElement(aut_inf, "txt").text = reason_title
            ET.SubElement(aut_inf, "read_txt").text = reason_desc


        auth_result_data =  bytearray(bytes.fromhex("000000000000000000010f01"))
        if auth_result is False:
            auth_result_data[11] = 2


        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "AP"})
        ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": "AUTHRESULT.001"})

        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)
        files.append(("response.xml", xml_str.encode("utf-8"),))
        files.append(("AUTHRESULT.001", auth_result_data,))

        return compress_carwings(construct_carwings_filepacket(files))
    return None