import xml.etree.ElementTree as ET
from xml.dom import minidom


def carwings_create_xmlfile_content(root: ET.Element):
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="")

    xml_declaration = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    return xml_declaration + pretty_xml.split('\n', 1)[1]

def parse_carwings_xml(xml_string: str) -> dict:
    """
    Parse CARWINGS XML message and return structured data as a dictionary.

    Args:
        xml_string: XML string to parse

    Returns:
        Dictionary containing parsed data
    """
    # Parse XML string
    root = ET.fromstring(xml_string)

    # Initialize result dictionary
    result = {
        'version': root.get('version'),
        'service_info': {},
        'operation_info': {}
    }

    # Parse authentication info
    aut_inf = root.find('aut_inf')
    if aut_inf is not None:
        result['authentication'] = {
            'navi_id': aut_inf.get('navi_id'),
            'tel': aut_inf.get('tel'),
            'dcm_id': aut_inf.get('dcm_id'),
            'sim_id': aut_inf.get('sim_id'),
            'vin': aut_inf.get('vin'),
            'user_id': aut_inf.get('user_id'),
            'password': aut_inf.get('password')
        }

    # Parse base info
    bs_inf = root.find('bs_inf')
    if bs_inf is not None:
        result['base_info'] = {}
        # Software version
        sftwr_ver = bs_inf.find('sftwr_ver')
        if sftwr_ver is not None:
            result['base_info']['software'] = {
                'navi': sftwr_ver.get('navi'),
                'map': sftwr_ver.get('map'),
                'dcm': sftwr_ver.get('dcm')
            }

        # Vehicle info
        vcl = bs_inf.find('vcl')
        if vcl is not None:
            vehicle_data = {
                'speed': vcl.get('spd'),
                'direction': vcl.get('drc'),
                'status': vcl.get('sts'),
                'rss': vcl.get('rss'),
                'odometer': vcl.get('odo'),
                'distance': vcl.get('dst'),
                'carrier': vcl.get('crr'),
                'energy_mileage': vcl.get('e_mlg')
            }

            # Coordinates
            crd = vcl.find('crd')
            if crd is not None:
                vehicle_data['coordinates'] = {
                    'datum': crd.get('datum'),
                    'latitude': crd.get('lat'),
                    'longitude': crd.get('lon')
                }

            result['base_info']['vehicle'] = vehicle_data

        # Navigation settings
        navi_set = bs_inf.find('navi_set')
        if navi_set is not None:
            result['base_info']['navigation_settings'] = {
                'time_zone': navi_set.get('t_zone'),
                'language': navi_set.get('lang'),
                'distance_display': navi_set.get('dst_d'),
                'temperature_display': navi_set.get('tmp_d'),
                'energy_mileage_display': navi_set.get('e_mlg_d'),
                'speed_display': navi_set.get('spd_d')
            }

    # Parse service info
    srv_inf = root.find('srv_inf')
    if srv_inf is not None:
        result['service_info'] = {}
        app = srv_inf.find('app')
        if app is not None:
            result['service_info']['application'] = {
                'name': app.get('name')
            }
            send_data = app.find('send_data')
            if send_data is not None:
                result['service_info']['application']['send_data'] = {
                    'id_type': send_data.get('id_type'),
                    'id': send_data.get('id')
                }

    # Parse operation info
    op_inf = root.find('op_inf')
    if op_inf is not None:
        result['operation_info'] = {}
        via_dst = op_inf.find('via_dst')
        if via_dst is not None:
            result['operation_info']['via_destination'] = {
                'set_number': via_dst.get('set_number'),
                'guide_status': via_dst.get('gid_sts')
            }

        rd_point = op_inf.find('rd_point')
        if rd_point is not None:
            result['operation_info']['road_point'] = {
                'full': rd_point.get('full'),
                'max': rd_point.get('max'),
                'used_number': rd_point.get('usd_num')
            }

        tinf_cnd = op_inf.find('tinf_cnd')
        if tinf_cnd is not None:
            result['operation_info']['traffic_info_condition'] = {
                'auto_cm': tinf_cnd.get('auto_cm'),
                'cm_interval': tinf_cnd.get('cm_intrvl'),
                'probe': tinf_cnd.get('probe'),
                'vics': tinf_cnd.get('vics'),
                'dynamic_calculation': tinf_cnd.get('dynmc_cal'),
                'status_info': tinf_cnd.get('sts_inf')
            }

        app_id = op_inf.find('app_id')
        if app_id is not None:
            result['operation_info']['app_id'] = app_id.get('is')

    return result