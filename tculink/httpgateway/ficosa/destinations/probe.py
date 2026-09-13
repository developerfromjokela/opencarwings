import csv
import io
import logging
import os
import random
import uuid
from datetime import datetime
from django.core.files.base import ContentFile
import tculink.gdc_proto.ficosa.acp as acp
from db.models import Car, DOTFile
from tculink.carwings_proto.probe_crm import crm_labelmap, sections, parse_crm_datablocks, update_crm_to_db
from tculink.carwings_proto.probe_dot import prb_dotfiletypes, parse_dotfile
from tculink.gdc_proto.acp245.parser import decode_probe_form_item
from tculink.gdc_proto.ficosa.probe import make_crm_parsing_block_v2

logger = logging.getLogger("ficosa")


def save_debug_data(tcu_gen, block, block_id, fulldata, req_id):
    log_dir = os.path.join("logs", "probev2", tcu_gen,
                           datetime.now().strftime('%Y%m%d%H%M'))
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, f"fulldata-{req_id}.bin")
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(fulldata)

    file_path = os.path.join(log_dir, f"block-{block_id}-{block_id:04x}-{req_id}.bin")
    with open(file_path, "wb") as f:
        f.write(block)




def handle(bin_data: bytes, acp_data: dict, car: Car, source_id: int, destination_id: int) -> bytes:
    """
    Process probe information
    """
    unique_req_id = random.randrange(111111, 999999, 6)
    tcu_gen = acp_data["veh_desc"].get("dcm", "UNKNOWN")
    offset = 0
    # data types: alertdata & journey data = 2, trackdata = 5, 1 = statusdata
    # datatype 5 sent at ignition off with 0xee, at start 0xed
    #
    probe_header, consumed = acp.parser.decode_probe_header(bin_data, offset)
    offset += consumed

    timestamp, consumed = acp.parser.decode_timestamp(bin_data, offset)
    offset += consumed

    probe_data, _ = acp.parser.decode_probe_data(bin_data, offset)


    if probe_header["data_type"] == 5:
        car.ev_info.car_running = destination_id == 0xed
        car.ev_info.charging = False
        car.ev_info.plugged_in = False
        car.ev_info.save()

    # Service types, 0x50 = latest, 0x51 = trip info, charging etc. 0x52 = unknown new fields, 0x53 = DOT data
    probe_service = probe_data["type"]
    binary_data = probe_data["data"]
    datablocks = []
    i = 0

    if probe_service == 0x53:
        dot_data = bytearray()
        while i < len(binary_data):
            new_itm, li = decode_probe_form_item(binary_data, i)
            block_length = new_itm["length"]
            if block_length > 0:
                block_data = new_itm["data"]
                if block_data[0] in prb_dotfiletypes:
                    dot_data.extend(block_data)
            i += li

        parsed_dot_info = parse_dotfile(dot_data, ficosa=True)
        gps_time = next((x["GPS time"] for x in parsed_dot_info if "GPS time" in x), None)
        csv_file = io.StringIO()
        fieldnames = [x[0] for x in list(prb_dotfiletypes.values())]
        fieldnames.append("road_type")
        fieldnames.append("road_collected")
        fieldnames.append("GPS time_raw")
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed_dot_info)
        content = csv_file.getvalue().encode('utf-8')
        csv_file_obj = ContentFile(content, name=f"DOT-{uuid.uuid4()}.csv")
        dot_dbrecord = DOTFile()
        dot_dbrecord.car = car
        dot_dbrecord.file = csv_file_obj
        dot_dbrecord.capture_ts = gps_time
        dot_dbrecord.save()
    else:
        while i < len(binary_data):
            new_itm, li = decode_probe_form_item(binary_data, i)
            block_length = new_itm["length"]
            block_id = new_itm["id"]
            if block_length > 0:
                block_data = new_itm["data"]
                if block_data[0] == 1:
                    # New FICOSA Type
                    data_id = int.from_bytes([block_data[0], block_data[1]], byteorder="big", signed=False)
                    ficosa_block = make_crm_parsing_block_v2(data_id, block_data[2:])
                    if ficosa_block is None:
                        logger.warning("FICOSA CRM block not found, %d, %d", data_id, block_length)
                        try:
                            save_debug_data(tcu_gen, block_data, data_id, bin_data, unique_req_id)
                        except:
                            pass
                    else:
                        datablocks.append(ficosa_block)
                elif block_data[0] not in crm_labelmap:
                    logger.warning("CRM block not found, %d, %d", block_id, block_length)
                    try:
                        save_debug_data(tcu_gen, block_data, block_id, bin_data, unique_req_id)
                    except:
                        pass
                else:
                    meta = crm_labelmap[block_data[0]]
                    datablocks.append({
                        "type": block_data[0],
                        "struct": sections[meta["structure"]],
                        "data": block_data[1:]
                    })

            i += li

        parsed_crm_info = parse_crm_datablocks(datablocks)

        # only one trip at a time. merge all separate trip objects into one
        if probe_service == 0x51:
            if "trips" in parsed_crm_info and len(parsed_crm_info["trips"]) > 0:
                unified_trip = {k: v for d in parsed_crm_info["trips"] for k, v in d.items()}
                parsed_crm_info["trips"] = [unified_trip]

        update_crm_to_db(car, parsed_crm_info)

    return acp.make_ack_response(car.vin, car.tcu_model, destination_id, source_id, 0, 0, 1)
