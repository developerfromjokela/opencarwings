import logging
import os
import random
from datetime import datetime

import tculink.gdc_proto.ficosa.acp as acp
from db.models import Car
from tculink.carwings_proto.probe_crm import crm_labelmap, sections, parse_crm_datablocks, update_crm_to_db
from tculink.gdc_proto.acp245.parser import decode_probe_form_item

logger = logging.getLogger("ficosa")


def save_debug_data(tcu_gen, block, block_id, fulldata, req_id):
    log_dir = os.path.join("logs", "probev2", tcu_gen,
                           datetime.now().strftime('%Y%m%d%H%M'))
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, f"fulldata-{req_id}.bin")
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(fulldata)

    file_path = os.path.join(log_dir, f"block-{block_id}-{req_id}.bin")
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

    probe_service = probe_data["type"]

    # Service types, 0x50 = latest, 0x51 = trip info, charging etc. 0x52 = unknown, new fields

    if probe_service == 0x53:
        # TODO DOT, requires special handling
        pass
    else:
        binary_data = probe_data["data"]
        datablocks = []
        i = 0
        print(len(binary_data), probe_data)
        while i < len(binary_data):
            new_itm, li = decode_probe_form_item(binary_data, i)
            block_length = new_itm["length"]
            block_id = new_itm["id"]
            print(new_itm)
            if block_length > 0:
                block_data = new_itm["data"]
                if block_data[0] not in crm_labelmap:
                    logger.warning("CRM block not found, %d, %d", block_id, block_length)
                    try:
                        save_debug_data(tcu_gen, block_data, block_id, bin_data, unique_req_id)
                    except:
                        pass
                else:
                    # skip element 0xb9, it is somewhat different and not parsing right
                    if block_data[0] != 0xb9:
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
