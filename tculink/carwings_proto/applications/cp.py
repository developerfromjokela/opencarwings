import datetime
import logging
import requests
from unidecode import unidecode
from django.conf import settings
import xml.etree.ElementTree as ET

from tculink.carwings_proto.databuffer import construct_carwings_filepacket, compress_carwings
from tculink.carwings_proto.dataobjects import create_cpinfo, construct_dms_coordinate
from tculink.carwings_proto.meshutils import read_big_endian_u_int32, unpack_monster_id_to_mesh_id, MeshPoint, MapPoint, \
    mesh_point_to_map_point
from tculink.carwings_proto.xml import carwings_create_xmlfile_content

logger = logging.getLogger("carwings_cp")

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def merge_bounding_boxes(bounding_boxes):
    if not bounding_boxes:
        return None

    min_lat = float('inf')
    max_lat = float('-inf')
    min_lon = float('inf')
    max_lon = float('-inf')

    for bbox in bounding_boxes:
        bottomleft_lat, bottomleft_lon = bbox[0]
        topleft_lat, topleft_lon = bbox[1]
        bottomright_lat, bottomright_lon = bbox[2]

        topright_lat = topleft_lat
        topright_lon = bottomright_lon

        current_lats = [bottomleft_lat, topleft_lat, bottomright_lat, topright_lat]
        current_lons = [bottomleft_lon, topleft_lon, bottomright_lon, topright_lon]

        min_lat = min(min_lat, min(current_lats))
        max_lat = max(max_lat, max(current_lats))
        min_lon = min(min_lon, min(current_lons))
        max_lon = max(max_lon, max(current_lons))

    # Create the merged bounding box in your format
    merged_bbox = [
        [min_lat, min_lon],  # bottom-left
        [max_lat, min_lon],  # top-left
        [min_lat, max_lon]  # bottom-right
    ]

    return merged_bbox


def point_in_bounding_box(lat, lon, bbox):
    bottomleft_lat, bottomleft_lon = bbox[0]
    topleft_lat, topleft_lon = bbox[1]
    bottomright_lat, bottomright_lon = bbox[2]

    # Extract the bounds
    min_lat = min(bottomleft_lat, topleft_lat, bottomright_lat)
    max_lat = max(bottomleft_lat, topleft_lat, bottomright_lat)
    min_lon = min(bottomleft_lon, topleft_lon, bottomright_lon)
    max_lon = max(bottomleft_lon, topleft_lon, bottomright_lon)

    # Check if point is within bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def find_containing_mesh_id(lat, lon, bounding_boxes):
    for mesh_id, bbox in bounding_boxes.items():
        if point_in_bounding_box(lat, lon, bbox):
            return mesh_id, bbox
    return None, None

def handle_cp(xml_data, files):
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

        files = []


        req_id = int.from_bytes(file_content[4:6], byteorder="big")
        logger.info("CP Request ID %d", req_id)
        if req_id == 277:
            count = int.from_bytes(file_content[6:10], byteorder="big")

            data = file_content[10:]

            mesh_bounding_boxes = {}

            for i in range(int(count)):
                buffer = data[(i * 4):(i * 4) + 4]
                value = read_big_endian_u_int32(buffer)
                decoded_mesh_id = unpack_monster_id_to_mesh_id(value)

                base_meshpoint = MeshPoint()
                base_meshpoint.meshID = decoded_mesh_id
                base_meshpoint.x = 0
                base_meshpoint.y = 0

                base_map_point = MapPoint()
                tl_map_point = MapPoint()
                bl_map_point = MapPoint()

                # bottom left aka. base point
                if not mesh_point_to_map_point(base_meshpoint, base_map_point):
                    continue
                # top left
                base_meshpoint.x = 0x7ff
                base_meshpoint.y = 0
                if not mesh_point_to_map_point(base_meshpoint, tl_map_point):
                    continue
                # bottom right
                base_meshpoint.x = 0
                base_meshpoint.y = 0x7ff
                if not mesh_point_to_map_point(base_meshpoint, bl_map_point):
                    continue

                mesh_bounding_boxes[value.value] = [
                    [float((base_map_point.lat / 512.0) / 3600.0), float((base_map_point.lon / 512.0) / 3600.0)],
                    [float((tl_map_point.lat / 512.0) / 3600.0), float((tl_map_point.lon / 512.0) / 3600.0)],
                    [float((bl_map_point.lat / 512.0) / 3600.0), float((bl_map_point.lon / 512.0) / 3600.0)],
                ]

            bbox = merge_bounding_boxes(list(mesh_bounding_boxes.values()))
            boundingbox_tl = "(" + (",".join([str(x) for x in bbox[1]])) + ")"
            boundingbox_br = "(" + (",".join([str(x) for x in bbox[2]])) + ")"
            logger.info("TOP LEFT: %s", boundingbox_tl)
            logger.info("BOTTOM RIGHT: %s", boundingbox_br)
            chargers_resp = requests.get('https://api.openchargemap.io/v3/poi', params={
                'client': 'OpenCARWINGS',
                'compact': 'true',
                # Type 1,2 & Chademo
                'connectiontypeid': '2,1,25',
                'boundingbox': ",".join([str(boundingbox_tl), str(boundingbox_br)]),
                'maxresults': "10000",
            }, headers={'X-API-Key': settings.OPENCHARGEMAP_API_KEY}).json()
            logger.info("Charger list query: %d", len(chargers_resp))

            chargers_per_meshid = {}

            for charger in chargers_resp:
                # charger_ids.append(str(charger['ID']))
                data = charger['ID'].to_bytes(4, 'big')
                # Calculate revision info based on last modification day
                tstamp = abs(datetime.datetime.fromisoformat(charger['DateLastVerified'].replace("Z", "")).timestamp() - datetime.datetime(2020, 1, 1, 0, 0, 0).timestamp())
                data += int(tstamp).to_bytes(4, 'big')
                data += construct_dms_coordinate(charger['AddressInfo']['Latitude'],
                                                 charger['AddressInfo']['Longitude'])
                mesh_id, bbox = find_containing_mesh_id(charger['AddressInfo']['Latitude'],
                                                             charger['AddressInfo']['Longitude'], mesh_bounding_boxes)
                if bbox is None:
                    logger.warning("No bounding box found: %d", charger['ID'])
                    continue
                if mesh_id not in chargers_per_meshid:
                    chargers_per_meshid[mesh_id] = [data]
                else:
                    chargers_per_meshid[mesh_id].append(data)

            logger.debug("Total processed meshIDs: %d", len(chargers_per_meshid.keys()))

            for mesh_id, chargers in chargers_per_meshid.items():
                logger.debug("Mesh ID: %d, chargers: %d", mesh_id, len(chargers))
                data = b'\x00' * 9
                data += b'\x01\x15'
                data += b'\x00'
                data += mesh_id.to_bytes(4, 'big')
                data += len(chargers).to_bytes(4, 'big')
                for charger in chargers:
                    data += charger
                files.append(data)

        elif req_id == 276:

            count = int.from_bytes(file_content[6:10], byteorder="big")

            data = file_content[10:]

            charger_ids = []

            for i in range(int(count)):
                charger_ids.append(str(int.from_bytes(data[(i * 4):(i * 4) + 4], byteorder="big")))

            logger.info("get CPINFO! %d", len(charger_ids))

            chargers_info = []

            for chunk in chunks(charger_ids, 150):
                chargers_resp = requests.get('https://api.openchargemap.io/v3/poi', params={
                    'client': 'OpenCARWINGS',
                    'chargepointid': ",".join(chunk),
                    'compact': 'false',
                    'maxresults': "150"
                }, headers={'X-API-Key': settings.OPENCHARGEMAP_API_KEY})
                chargers_resp = chargers_resp.json()
                logger.debug((len(chargers_resp)))
                chargers_info = chargers_info + chargers_resp

            logger.info("TOTAL CP INFO: %d", len(chargers_info))
            # resp_file = bytes.fromhex('00 00 00 00 00 00 00 00 00 01 14 05 05 05 03 03 54 53 54 03 44 45 46 03 47 48 49 03 4A 4B 4C 03 4D 4E 4F 03 41 41 41 03 42 42 42 03 43 43 43 03 43 43 43 80 00 0A 29 08 F3 3B 2B 10 0F 08 44 45 53 43 44 45 53 43 59 E9 9D 12 03 45 45 45 00 00 00 01 80 00 0A 29 08 F3 3B 2B 10 0F 03 54 61 67 01 02 3F 3F 01 02 44 44 01 02 45 45 01 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'.replace(' ', ''))
            # normal:
            # resp_file = bytes.fromhex('FF FF FF FF FF FF FF 00 00 01 14 05 05 05 03 17 4C 61 64 65 73 74 61 73 6A 6F 6E 20 66 6F 72 20 65 6C 62 69 6C 65 72 04 30 30 31 32 04 4F 73 6C 6F 04 4F 73 6C 6F 0A 4E 6F 72 64 73 74 72 61 6E 64 00 00 00 00 80 00 0A 29 08 F3 3B 2B 10 0F 0B 40 56 61 72 73 76 69 6E 67 65 6E 59 E9 9D 12 00 00 01 00 00 00 00 01 03 A2 03 00 00 02 00 00 16 33 20 33 3B 40 3B 2A 3B 24 31 32 3B 26 31 3B 21 3B 25 3B 3F 3B 23 00'.replace(' ', ''))
            # resp_file = bytes.fromhex('FF FF FF FF FF FF FF 00 00 01 14 05 05 05 03 05 53 68 65 6C 6C 04 30 30 31 32 04 4F 73 6C 6F 04 4F 73 6C 6F 0A 4E 6F 72 64 73 74 72 61 6E 64 00 00 00 00 80 00 0A 29 08 F3 3B 2B 10 0F 0E 31 40 4E 79 71 75 69 73 74 76 65 69 65 6E 59 E9 9D 12 0E 2B 28 34 37 29 2D 32 32 32 38 32 32 30 39 00 01 00 00 00 00 01 01 03 03 00 00 02 00 00 16 31 20 33 3B 40 3B 2A 3B 24 31 32 3B 26 32 3B 21 3B 25 3B 3F 3B 23 00'.replace(' ', ''))

            for charger in chargers_info:
                station_qc_type = 3
                station_ac_type = 3
                if next((plug for plug in charger["Connections"] if plug["ConnectionTypeID"] == 2), None) is not None:
                    station_qc_type = 1
                else:
                    station_ac_type = 177

                # OCM doesn't provide opening hours, set &3
                config_params = ["*", "$11", "&3", "!", "%", "?", "#"]

                if charger.get("UsageTypeID", 0) == 0:
                    config_params.insert(0, "3")
                elif charger.get("UsageTypeID", 0) in [2, 5, 6]:
                    config_params.insert(0, "1")
                else:
                    config_params.insert(0, "2")

                conf_str = f"{station_qc_type} "
                conf_str += ";".join(config_params)

                phone_num = ((charger.get("AddressInfo", None) or {}).get("ContactTelephone1", "")) or ""
                if len(phone_num) < 1:
                    phone_num = ((charger.get("OperatorInfo", None) or {}).get("PhonePrimaryContact", "")) or ""

                cpinfo_obj = {
                    'poi_id': charger['ID'],
                    'name': unidecode(charger['AddressInfo'].get('Title', 'Charging Station') or "Charging Station")[:30],
                    'code': '',
                    'county': unidecode(charger["AddressInfo"].get("Town", '') or "")[:30],
                    'region': unidecode(charger["AddressInfo"].get('StateOrProvince', '') or "")[:30],
                    'city': unidecode(charger["AddressInfo"].get("Town", '') or "")[:30],
                    'town': unidecode(charger["AddressInfo"].get("Postcode", '') or "")[:30],
                    'meta1': '',
                    'meta2': '',
                    'meta3': '',
                    'lat': charger["AddressInfo"]["Latitude"],
                    'lon': charger["AddressInfo"]["Longitude"],
                    'address': unidecode(charger["AddressInfo"].get("AddressLine1", "") or "")[:30],
                    'mesh_id': 65535,
                    'phone': phone_num,
                    'sites': [],
                    'stations': [
                        {
                            'flag1': 1,
                            # 1 -> DC fast charge, anything else -> not fast
                            'fast_flag': station_qc_type,
                            # 3 -> no slow, 180 -> New type 20, 179 -> New type 19, 178 -> Mode 3, type 3 socket. 177 -> Mode 3, type 1. 176 -> Blue industrial socket
                            'slow_flag': station_ac_type,
                            # stations count?
                            'flag2': charger["NumberOfPoints"] or 1,
                            'flag3': 2,
                            'opt_desc': '',
                        }
                    ],
                    # 1 -> QC, 3 -> other
                    # 1 -> free, 2 -> charged, 3 -> none
                    # &1 -> 24h, &2 -> custom time using?, &3 -> ?
                    # ? -> ??
                    # @ -> ??
                    # # -> opening time showing flag, optinally days: 1->mon,2->tue, _ delimiter, times: 06:00-24:00, also possible multiple times, daynums_time
                    #
                    'config_str': conf_str
                }
                logger.info(cpinfo_obj)
                files.append(create_cpinfo(cpinfo_obj))

        cws_files = []

        carwings_xml_root = ET.Element("carwings", version="2.2")
        ET.SubElement(carwings_xml_root, "aut_inf", {"sts": "ok"})

        srv_inf = ET.SubElement(carwings_xml_root, "srv_inf")
        app_elm = ET.SubElement(srv_inf, "app", {"name": "CP"})

        for idx, file in enumerate(files):
            flname = f"CPLIST.{idx + 1}"
            cws_files.append((flname, file))
            ET.SubElement(app_elm, "send_data", {"id_type": "file", "id": flname})

        op_inf = ET.SubElement(carwings_xml_root, "op_inf")
        ET.SubElement(op_inf, "timing", {"req": "normal"})

        xml_str = carwings_create_xmlfile_content(carwings_xml_root)

        cws_files.insert(0, ("response.xml", xml_str.encode("utf-8"),))

        return compress_carwings(construct_carwings_filepacket(cws_files))


    return None
