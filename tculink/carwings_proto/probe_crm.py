from db.models import Car, CRMLatest, CRMLifetime, CRMExcessiveAirconRecord, CRMExcessiveIdlingRecord, CRMMonthlyRecord, \
    CRMMSNRecord, CRMChargeRecord, CRMChargeHistoryRecord, CRMABSHistoryRecord, CRMTroubleRecord, CRMTripRecord, \
    CRMDistanceRecord
from tculink.carwings_proto.crm_labels import CRM_LABELS
import logging
logger = logging.getLogger("probe")
from tculink.carwings_proto.utils import parse_std_location
import struct
import json
import datetime
from django.utils import timezone

# section IDs mapped to a name
sections = {
    1: "latest",
    2: "lifetime",
    3: "trips",
    4: "monthly",
    5: "distance",
    6: "idling",
    7: "aircon",
    8: "msn",
    9: "charge",
    10: "trouble",
    11: "absdata",
    12: "chargehistory",
}

# which label is first item in the block
first_blocks = {
    "latest": 0xE1,
    "lifetime": 0xE6,
    "trips": 0x80,
    "monthly": 0xA0,
    "idling": 0xBD,
    "aircon": 0xBE,
    "msn": 0xC4,
    "absdata": 0xCC,
    "charge": 0xC5,
    "chargehistory": 0xDA,
    "trouble": 0xF8,
    "distance": 0xB8
}

crm_labelmap = {}
for item in CRM_LABELS:
    label = int(item["label"], 16)
    crm_labelmap[label] = {
        "size": int(item["dataSize"], 16),
        "type": int(item["dataType"], 16),
        "structure": int(item["dataStructur"], 16),
        "judgement": int(item["judgementType"], 16),
    }

def parse_crmfile(data):
    # skip header
    dotfile_data = bytearray(data[38:])

    if dotfile_data[0] != 0xE1:
        raise Exception("Invalid CRM file!")

    pos = 0
    parsingblocks = []

    while pos < len(dotfile_data):
        item_type = dotfile_data[pos]
        if item_type in crm_labelmap:
            meta = crm_labelmap[item_type]
            size = meta["size"]
            logger.debug("Label: %d,%s", item_type, hex(item_type))
            logger.debug("Datafield type: %d", meta["type"])
            if meta["type"] == 7:
                size_field = dotfile_data[pos + 1]
                logger.debug("Block count: %d", size_field)
                size = 6 * size_field
                logger.debug("Size: %s", hex(size))
                if size == 0:
                    size += 1
                size = size+2
            elif meta["type"] == 0x10:
                size_field = dotfile_data[pos + 7]
                logger.debug("MSN Byte count: %s", size_field)
                logger.debug("Size: %s", hex(size))
                size = size+8
            elif meta["type"] == 0x11:
                size_field = dotfile_data[pos + 1]
                logger.debug("Block count: %d", size_field)
                size = 30 * size_field
                logger.debug("Size: %s", hex(size))
                size = size+2
            elif meta["type"] == 0x12 or meta["type"] == 0x13\
                    or meta["type"] == 0x14 or meta["type"] == 0x15:
                size_field = dotfile_data[pos + 1]
                logger.debug("Block count: %d", size_field)
                size = 18 * size_field
                logger.debug("Size: %s", hex(size))
                size = size+2
            elif meta["type"] == 0x17:
                size_field = dotfile_data[pos + 1]
                logger.debug("Block count: %d", size_field)
                size = 25 * size_field
                logger.debug("Size: %s", hex(size))
                size = size+2
            logger.debug("DATALEN: %d",size-1)
            parsingblocks.append({
                "type": item_type,
                "struct": sections[meta["structure"]],
                "data": dotfile_data[pos + 1:pos + size],
            })
            # advance one byte if empty
            if size == 0:
                pos += 1
            else:
                pos += size
            logger.debug("-------------------")
        else:
            raise Exception("UNKNOWN TYPE: ",item_type,"HEX", hex(item_type), "pos:",pos)

    logger.info("-- Start parsing crmblocks --")

    parse_result = {
        "latest": {},
        "lifetime": {},
        "trips": [],
        "monthly": [],
        "aircon": [],
        "idling": [],
        "msn": [],
        "absdata": [],
        "charge": [],
        "chargehistory": [],
        "trouble": [],
        'distance': []
    }

    currentblock = None
    draft_struct = {}

    for crmblock in parsingblocks:
        if currentblock is None:
            logger.debug("Starting to parse crmblock %s", crmblock["struct"])
            currentblock = crmblock["struct"]
        elif currentblock != crmblock["struct"]:
            logger.debug("Block change, closing block: %s", currentblock)
            if isinstance(parse_result[currentblock], dict):
                parse_result[currentblock] = draft_struct
            else:
                parse_result[currentblock].append(draft_struct)
            draft_struct = {}
            currentblock = crmblock["struct"]
        elif crmblock["type"] in list(first_blocks.values()):
            logger.info("Identified head item! saving previous object and opening new")
            if len(draft_struct.keys()) > 0:
                if isinstance(parse_result[currentblock], dict):
                    parse_result[currentblock] = draft_struct
                else:
                    parse_result[currentblock].append(draft_struct)
            draft_struct = {}
            currentblock = crmblock["struct"]

        logger.info("Block %d", crmblock["type"])
        block_data = crmblock["data"]

        # latest
        if crmblock["type"] == 0xE1:
            draft_struct["phone_contacts_saved"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0xE2:
            draft_struct["navi_points_saved"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0xEA:
            draft_struct["odometer"] = int.from_bytes(block_data, byteorder="big")
            continue

        # lifetime
        if crmblock["type"] == 0xE6:
            draft_struct["aircon_usage"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0xE7:
            draft_struct["headlight_on_time"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0xE8:
            draft_struct["average_speed"] = int.from_bytes(block_data, byteorder="big")/10.0
            continue
        if crmblock["type"] == 0xE9:
            draft_struct["regen"] = int.from_bytes(block_data[:4], byteorder="big")
            draft_struct["consumption"] = int.from_bytes(block_data[4:8], byteorder="big")
            continue
        if crmblock["type"] == 0xEB:
            draft_struct["running_time"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0xED:
            draft_struct["mileage"] = int.from_bytes(block_data, byteorder="big")/100.0
            continue

        # aircon and idling
        if crmblock["type"] == 0xBE:
            draft_struct["start"] = datetime.datetime(2000+block_data[0], block_data[1],block_data[2], block_data[3],
                                                     block_data[4], block_data[5], block_data[6])
            draft_struct["consumption"] = int.from_bytes(bytearray(block_data[8:9]), byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xBD:
            draft_struct["start"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5], block_data[6])
            draft_struct["duration"] = int.from_bytes(bytearray(block_data[8:9]), byteorder="big", signed=False)
            continue

        # monthly
        if crmblock["type"] == 0xA0:
            if block_data[1] < 1:
                block_data[1] = 1
            if block_data[2] < 1:
                block_data[2] = 1
            draft_struct["start"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2])
            continue
        if crmblock["type"] == 0xA1:
            if block_data[1] < 1:
                block_data[1] = 1
            if block_data[2] < 1:
                block_data[2] = 1
            draft_struct["end"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2])
            continue
        if crmblock["type"] == 0xA3:
            draft_struct["distance"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xA4:
            draft_struct["drive_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xA5:
            draft_struct["average_speed"] = int.from_bytes(block_data, byteorder="big", signed=False)/10.0
            continue
        if crmblock["type"] == 0xA9:
            draft_struct["p_range_freq"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xAB:
            draft_struct["r_range_freq"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xAF:
            draft_struct["trip_count"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xB1:
            braking_speeds = []
            for i in range(24):
                speed = int.from_bytes(block_data[2*i:(i+1)*2], byteorder="big", signed=False)
                if speed != 0:
                    braking_speeds.append(speed)
            draft_struct["braking_speeds"] = braking_speeds
            continue
        if crmblock["type"] == 0xB3:
            draft_struct["regen_total_wh"] = int.from_bytes(block_data[:4], byteorder="big", signed=False)
            draft_struct["consumed_total_wh"] = int.from_bytes(block_data[4:8], byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xB4:
            start_stop_distances = []
            for i in range(36):
                dist = int.from_bytes(block_data[2*i:(i+1)*2], byteorder="big", signed=False)
                if dist != 0:
                    start_stop_distances.append(dist)
            draft_struct["start_stop_distances"] = start_stop_distances
            continue
        if crmblock["type"] == 0xB7:
            draft_struct["average_accel"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xD8:
            draft_struct["n_range_freq"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xD9:
            draft_struct["b_range_freq"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xB5:
            switch_usage = []
            count = block_data[0]
            if (len(block_data)-1)/4 != count:
                logger.warning("WARN! mismatch block size")
                continue
            for i in range(count+1):
                usage_item = block_data[i*4:(i+1)*4]
                switch_usage.append({
                    "unit_id": usage_item[0],
                    "function_id": usage_item[1],
                    "switch_id": usage_item[2],
                    "number_of_operations": usage_item[3]
                })
            draft_struct["switch_usage_parked"] = switch_usage
            continue
        if crmblock["type"] == 0xB6:
            switch_usage = []
            count = block_data[0]
            if (len(block_data)-1)/4 != count:
                logger.warning("WARN! mismatch block size")
                continue
            for i in range(count+1):
                usage_item = block_data[i*4:(i+1)*4]
                switch_usage.append({
                    "unit_id": usage_item[0],
                    "function_id": usage_item[1],
                    "switch_id": usage_item[2],
                    "number_of_operations": usage_item[3]
                })
            draft_struct["switch_usage_driving"] = switch_usage
            continue

        # trip
        if crmblock["type"] == 0x80:
            draft_struct["start"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5])
            continue
        if crmblock["type"] == 0x81:
            draft_struct["stop"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5])
            continue
        if crmblock["type"] == 0x82:
            location = parse_std_location(struct.unpack('>i',block_data[0:4])[0], struct.unpack('>i',block_data[4:9])[0])
            draft_struct["start_location"] = {"lat": location[0], "lon": location[1]}
            continue
        if crmblock["type"] == 0x83:
            location = parse_std_location(struct.unpack('>i',block_data[0:4])[0], struct.unpack('>i',block_data[4:9])[0])
            draft_struct["stop_location"] = {"lat": location[0], "lon": location[1]}
            continue
        if crmblock["type"] == 0x85:
            draft_struct["distance"] = int.from_bytes(block_data, byteorder="big", signed=False)/1000.0
            continue
        if crmblock["type"] == 0x86:
            draft_struct["sudden_accelerations"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x87:
            draft_struct["sudden_decelerations"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x88:
            draft_struct["expressway_optional_speed_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x89:
            draft_struct["aircon_usage_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x8A:
            draft_struct["highway_driving_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x8B:
            draft_struct["idling_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x8C:
            draft_struct["average_speed"] = int.from_bytes(block_data, byteorder="big", signed=False)/10.0
            continue
        if crmblock["type"] == 0x90:
            draft_struct["outside_temp_start"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0x91:
            draft_struct["outside_temp_stop"] = int.from_bytes(block_data, byteorder="big")
            continue
        if crmblock["type"] == 0x92:
            draft_struct["time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x95:
            draft_struct["regen"] = int.from_bytes(block_data[:4], byteorder="big", signed=False)
            draft_struct["aircon_consumption"] = int.from_bytes(block_data[4:8], byteorder="big", signed=False)
            draft_struct["auxiliary_consumption"] = int.from_bytes(block_data[8:12], byteorder="big", signed=False)
            draft_struct["motor_consumption"] = int.from_bytes(block_data[12:16], byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x96:
            draft_struct["headlignt_on_time"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x97:
            draft_struct["average_accel"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x98:
            draft_struct["start_odometer"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x9A:
            draft_struct["max_speed"] = int.from_bytes(block_data, byteorder="big", signed=False)/10
            continue
        if crmblock["type"] == 0xB8:
            location = parse_std_location(struct.unpack('>i',block_data[15:19])[0], struct.unpack('>i',block_data[19:23])[0])
            draft_struct = {
                'timestamp': datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5], block_data[6]),
                'consumed_wh': int.from_bytes(block_data[7:11], "big"),
                'regenerated_wh': int.from_bytes(block_data[11:15], "big"),
                'latitude': location[0],
                'longitude': location[1],
                "road_type": int.from_bytes(block_data[24:], "big"),
            }
            continue
        if crmblock["type"] == 0xB9:
            draft_struct["accelerator_work"] = {
                "sudden_start_consumption": int.from_bytes(block_data[:4], byteorder="big", signed=False),
                "sudden_start_timestamp": datetime.time(block_data[4], block_data[5], block_data[6], block_data[7]),
                "sudden_acceleration_consumption": int.from_bytes(block_data[8:12], byteorder="big", signed=False),
                "sudden_acceleration_timestamp": datetime.time(block_data[12], block_data[13], block_data[14], block_data[15]),
                "non_eco_deceleration_consumption": int.from_bytes(block_data[16:20], byteorder="big", signed=False),
                "non_eco_deceleration_timestamp": datetime.time(block_data[16], block_data[17], block_data[18], block_data[19]),
            }
            continue
        if crmblock["type"] == 0xBA:
            draft_struct["idle_consumption"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xBF:
            draft_struct["used_preheating"] = block_data[0] == 1
            continue
        if crmblock["type"] == 0xD3:
            sudden_starts = []
            items_count = block_data[0]
            for i in range(items_count):
                item_data = block_data[(i*18)+1:((i+1)*18)+1]
                logger.debug(item_data.hex())
                location = parse_std_location(struct.unpack('>i',item_data[10:14])[0], struct.unpack('>i',item_data[14:18])[0])
                sudden_starts.append({
                    "timestamp": datetime.time(item_data[0], item_data[1], item_data[2], item_data[3]),
                    "power_consumption": item_data[4:8],
                    "elapsed_time": item_data[8:12],
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["sudden_starts"] = sudden_starts
            continue
        if crmblock["type"] == 0xD4:
            sudden_accels = []
            items_count = block_data[0]
            for i in range(items_count):
                item_data = block_data[(i*18)+1:((i+1)*18)+1]
                location = parse_std_location(struct.unpack('>i',item_data[10:14])[0], struct.unpack('>i',item_data[14:18])[0])
                sudden_accels.append({
                    "timestamp": datetime.time(item_data[0], item_data[1], item_data[2], item_data[3]),
                    "power_consumption": int.from_bytes(item_data[4:8], "big"),
                    "elapsed_time": int.from_bytes(item_data[9:13], "big"),
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["sudden_accelerations_list"] = sudden_accels
            continue
        if crmblock["type"] == 0xD5:
            non_eco_decelerations = []
            items_count = block_data[0]
            for i in range(items_count):
                item_data = block_data[(i*18)+1:((i+1)*18)+1]
                location = parse_std_location(struct.unpack('>i',item_data[10:14])[0], struct.unpack('>i',item_data[14:18])[0])
                non_eco_decelerations.append({
                    "timestamp": datetime.time(item_data[0], item_data[1], item_data[2], item_data[3]),
                    "power_consumption": int.from_bytes(item_data[4:8], "big"),
                    "elapsed_time": int.from_bytes(item_data[8:12], "big"),
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["non_eco_decelerations"] = non_eco_decelerations
            continue
        if crmblock["type"] == 0xD6:
            non_constant_speeds = []
            items_count = block_data[0]
            for i in range(items_count):
                item_data = block_data[(i*18)+1:((i+1)*18)+1]
                location = parse_std_location(struct.unpack('>i',item_data[10:14])[0], struct.unpack('>i',item_data[14:18])[0])
                non_constant_speeds.append({
                    "timestamp": datetime.time(item_data[0], item_data[1], item_data[2], item_data[3]),
                    "power_consumption": int.from_bytes(item_data[4:8], "big"),
                    "elapsed_time": int.from_bytes(item_data[8:12], "big"),
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["non_constant_speeds"] = non_constant_speeds
            continue
        if crmblock["type"] == 0xD7:
            draft_struct["batt_info"] = {
                "temp_start": block_data[0],
                "soh_start": block_data[1],
                "wh_energy_start": int.from_bytes(block_data[2:5], byteorder="big", signed=False),
                "temp_end": block_data[5],
                "soh_end": block_data[6],
                "wh_energy_end": int.from_bytes(block_data[7:], byteorder="big", signed=False),
            }
            continue
        if crmblock["type"] == 0xDE:
            draft_struct["batt_degradation_analysis"] = {
                "energy_content_start": int.from_bytes(block_data[:2], byteorder="big", signed=False),
                "energy_content_end": int.from_bytes(block_data[2:4], byteorder="big", signed=False),
                "avg_temp_start": block_data[5],
                "max_temp_start": block_data[6],
                "min_temp_start": block_data[7],
                "avg_temp_end": block_data[8],
                "max_temp_end": block_data[9],
                "min_temp_end": block_data[10],
                "avg_cell_volt_start": block_data[11],
                "max_cell_volt_start": block_data[12],
                "min_cell_volt_end": block_data[13],
                "regen_end": block_data[14],
                "number_qc_charges": block_data[15],
                "number_ac_charges": block_data[16],
                "soc_end": block_data[16],
                "resistance_end": block_data[17],
            }
            continue
        if crmblock["type"] == 0xDF:
            draft_struct["eco_trees"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0xEE:
            draft_struct["batt_degradation_analysis_new"] = {
                "capacity_bars_end": block_data[0]
            }
            if len(block_data) > 1:
                draft_struct["batt_degradation_analysis_new"]["soc_end"] = block_data[1]
            continue

        # msn
        if crmblock["type"] == 0xC4:
            draft_struct["aquisition_ts"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5], block_data[6])
            draft_struct["data"] = block_data[18:]
            continue

        # charges
        if crmblock["type"] == 0xC5:
            items_count = block_data[0]
            if "charges" not in draft_struct:
                draft_struct["charges"] = []
            for i in range(items_count+1):
                location = parse_std_location(struct.unpack('>i',block_data[:4])[0], struct.unpack('>i',block_data[4:8])[0])
                charger_loc = parse_std_location(struct.unpack('>i',block_data[22:26])[0],struct.unpack('>i',block_data[26:30])[0])
                logger.debug(block_data[10:26])
                draft_struct["charges"].append({
                    "lat": location[0],
                    "long": location[1],
                    "charge_count": block_data[8],
                    "charge_type": block_data[9],
                    #"start_ts": (2000 + block_data[10], block_data[11], block_data[12], block_data[13],
                    #                                  block_data[14], block_data[15]),
                    #"end_ts": (2000 + block_data[16], block_data[17], block_data[18], block_data[19],
                    #                                  block_data[20], block_data[21]),
                    "charger_position_lat": charger_loc[0],
                    "charger_position_long": charger_loc[1],
                    "charger_position_flag": int.from_bytes(block_data[30:32], byteorder="big", signed=False)
                })
            continue

        # charge history
        if crmblock["type"] == 0xDA:
            draft_struct["charging_start"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5])
            draft_struct["charging_end"] = datetime.datetime(2000 + block_data[6], block_data[7], block_data[8], block_data[9],
                                                      block_data[10], block_data[11])
            draft_struct["remaining_charge_bars_at_start"] = block_data[12]
            draft_struct["remaining_charge_bars_at_end"] = block_data[13]
            draft_struct["remaining_gids_at_start"] = int.from_bytes(block_data[14:16], byteorder="big", signed=False)
            draft_struct["remaining_gids_at_end"] = int.from_bytes(block_data[16:18], byteorder="big", signed=False)
            draft_struct["power_consumption"] = int.from_bytes(block_data[18:20], byteorder="big", signed=False)
            draft_struct["charging_type"] = block_data[20]
            location = parse_std_location(struct.unpack('>i',block_data[21:25])[0], struct.unpack('>i',block_data[25:29])[0])
            draft_struct["lat"] = location[0]
            draft_struct["lon"] = location[1]
            draft_struct["batt_avg_temp_start"] = block_data[29]
            draft_struct["batt_max_temp_start"] = block_data[30]
            draft_struct["batt_min_temp_start"] = block_data[31]
            draft_struct["batt_avg_temp_end"] = block_data[32]
            draft_struct["batt_max_temp_end"] = block_data[33]
            draft_struct["batt_min_temp_end"] = block_data[34]
            draft_struct["batt_avg_cell_volt_start"] = block_data[35]
            draft_struct["batt_max_cell_volt_start"] = block_data[36]
            draft_struct["batt_min_cell_volt_end"] = block_data[37]
            draft_struct["current_accumulation_start"] = block_data[38]
            draft_struct["no_charges_while_ignoff"] = block_data[39]
            continue

        # abs
        if crmblock["type"] == 0xCC:
            draft_struct["abs_operation_start_ts"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2], block_data[3],
                                                      block_data[4], block_data[5])
            draft_struct["operation_time"] = block_data[6]
            draft_struct["vehicle_speed_at_start"] = int.from_bytes(block_data[7:9], byteorder="big", signed=False)
            location = parse_std_location(int.from_bytes(block_data[9:13], "big"), int.from_bytes(block_data[13:17], "big"))
            draft_struct["navi_pos_lat"] = location[0]
            draft_struct["navi_pos_lon"] = location[1]
            draft_struct["road_type"] = block_data[17]
            draft_struct["navi_direction"] = int.from_bytes(block_data[18:20], byteorder="big", signed=False)
            draft_struct["vehicle_speed_at_end"] = int.from_bytes(block_data[21:], byteorder="big", signed=False)
            continue

        # trouble
        if crmblock["type"] == 0xF8:
            trouble_count = block_data[0]
            records = []
            offset = 1  # Start after record_count


            def count_set_bits(value: int, num_bits: int = 16) -> int:
                count = 0
                for i in range(num_bits):
                    if value & (1 << i):
                        count += 1
                return count

            for _ in range(trouble_count):
                record_data = block_data[offset:offset + 25]
                unknown1 = int.from_bytes(record_data[0:10], byteorder="big", signed=False)
                bitfield1 = struct.unpack_from("<H", record_data, 10)[0]
                unknown2 = int.from_bytes(record_data[12:22], byteorder="big", signed=False)
                bitfield2 = struct.unpack_from("<H", record_data, 22)[0]

                # Calculate chkSize contribution
                bitfield1_set_bits = count_set_bits(bitfield1)
                bitfield2_set_bits = count_set_bits(bitfield2)

                records.append({
                    "timestamp": unknown1,
                    "basicinfo_judge": bitfield1,
                    "basicinfo_set_bits": bitfield1_set_bits,
                    "location": unknown2,
                    "warninginfo_judge": bitfield2,
                    "warninginfo_set_bits": bitfield2_set_bits,
                })

                offset += 25  # Advance to next record
            draft_struct["records"] = records


        logger.warning("  -> Unknown")
        draft_struct[hex(crmblock["type"])] = crmblock["data"].hex()

    # insert last block if available
    if len(draft_struct.keys()) > 0:
        if isinstance(parse_result[currentblock], dict):
            parse_result[currentblock] = draft_struct
        else:
            parse_result[currentblock].append(draft_struct)

    return parse_result

def apply_date_patch(date):
    # apply patch for gps rollover, add 1024 weeks
    rollover_timedelta = datetime.timedelta(days=1024*7)
    if date.year < timezone.now().year-5:
        return date + rollover_timedelta
    return date


def update_crm_to_db(car: Car, crm_pload):
    if car is None:
        raise Exception("car is None!")

    if "latest" in crm_pload and len(list(crm_pload["latest"].keys())) > 0:
        latest = crm_pload["latest"]
        try:
            latest_dbobj = CRMLatest.objects.get(car=car)
        except CRMLatest.DoesNotExist:
            latest_dbobj = CRMLatest()
            latest_dbobj.car = car
        latest_dbobj.odometer = latest.get("odometer", 0)
        latest_dbobj.phone_contacts = latest.get("phone_contacts_saved", 0)
        latest_dbobj.navi_points_saved = latest.get("navi_points_saved", 0)
        latest_dbobj.last_updated = timezone.now()
        latest_dbobj.save()

    if "lifetime" in crm_pload and len(list(crm_pload["lifetime"].keys())) > 0:
        lifetime = crm_pload["lifetime"]
        try:
            lifetime_dbobj = CRMLifetime.objects.get(car=car)
        except CRMLifetime.DoesNotExist:
            lifetime_dbobj = CRMLifetime()
            lifetime_dbobj.car = car
        lifetime_dbobj.aircon_usage = lifetime.get("aircon_usage", 0)
        lifetime_dbobj.headlight_on_time = lifetime.get("headlight_on_time", 0)
        lifetime_dbobj.average_speed = lifetime.get("average_speed", 0.0)
        lifetime_dbobj.regen = lifetime.get("regen", 0)
        lifetime_dbobj.consumption = lifetime.get("consumption", 0)
        lifetime_dbobj.running_time = lifetime.get("running_time", 0)
        lifetime_dbobj.mileage = lifetime.get("mileage", 0.0)
        lifetime_dbobj.last_updated = timezone.now()
        lifetime_dbobj.save()

    if "aircon" in crm_pload:
        for aircon in crm_pload["aircon"]:
            aircon_dbobj = CRMExcessiveAirconRecord()
            aircon_dbobj.car = car
            aircon_dbobj.start = apply_date_patch(aircon.get("start", datetime.datetime(1970, 1, 1)))
            aircon_dbobj.consumption = aircon.get("consumption", 0)
            aircon_dbobj.save()
    if "idling" in crm_pload:
        for idling in crm_pload["idling"]:
            idling_dbobj = CRMExcessiveIdlingRecord()
            idling_dbobj.car = car
            idling_dbobj.start = apply_date_patch(idling.get("start", datetime.datetime(1970, 1, 1)))
            idling_dbobj.duration = idling.get("duration", 0)
            idling_dbobj.save()

    if "monthly" in crm_pload:
        for monthly in crm_pload["monthly"]:
            monthly_db = CRMMonthlyRecord()
            monthly_db.car = car
            monthly_db.start = apply_date_patch(monthly.get("start", datetime.datetime(1970, 1, 1)))
            monthly_db.end = apply_date_patch(monthly.get("end", datetime.datetime(1970, 1, 1)))
            monthly_db.distance = monthly.get("distance", 0)
            monthly_db.drive_time = monthly.get("drive_time", 0)
            monthly_db.average_speed = monthly.get("average_speed", 0)
            monthly_db.p_range_freq = monthly.get("p_range_freq", 0)
            monthly_db.r_range_freq = monthly.get("r_range_freq", 0)
            monthly_db.n_range_freq = monthly.get("n_range_freq", 0)
            monthly_db.b_range_freq = monthly.get("b_range_freq", 0)
            monthly_db.trip_count = monthly.get("trip_count", 0)
            monthly_db.braking_speeds = monthly.get("braking_speeds", [])
            monthly_db.regen_total_wh = monthly.get("regen_total_wh", 0)
            monthly_db.consumed_total_wh = monthly.get("consumed_total_wh", 0)
            monthly_db.start_stop_distances = monthly.get("start_stop_distances", [])
            monthly_db.average_accel = monthly.get("average_accel", 0)
            monthly_db.switch_usage_parked = monthly.get("switch_usage_parked", [])
            monthly_db.switch_usage_driving = monthly.get("switch_usage_driving", [])
            monthly_db.save()

    if "msn" in crm_pload:
        for msn in crm_pload["msn"]:
            msn_db = CRMMSNRecord()
            msn_db.car = car
            msn_db.timestamp = apply_date_patch(msn.get("aquisition_ts", datetime.datetime(1970, 1, 1)))
            msn_db.data = {"v": 0, "data": hex(msn.get("data", bytearray()))}
            msn_db.save()

    if "charge" in crm_pload:
        for charge_row in crm_pload["charge"]:
            if "charges" in charge_row:
                for charge in charge_row["charges"]:
                    charge_db = CRMChargeRecord()
                    charge_db.car = car
                    charge_db.latitude = charge.get("lat", 0)
                    charge_db.longitude = charge.get("lon", 0)
                    charge_db.charge_count = charge.get("charge_count", 0)
                    charge_db.charge_type = charge.get("charge_type", 1)
                    charge_db.start_time = apply_date_patch(charge.get("start_ts", datetime.datetime(1970, 1, 1)))
                    charge_db.end_time = apply_date_patch(charge.get("end_ts", datetime.datetime(1970, 1, 1)))
                    charge_db.charger_position_latitude = charge.get("charger_position_lat", 0)
                    charge_db.charger_position_longitude = charge.get("charger_position_long", 0)
                    charge_db.save()

    if "chargehistory" in crm_pload:
        for chargehist in crm_pload["chargehistory"]:
            chargehist_db = CRMChargeHistoryRecord()
            chargehist_db.car = car
            chargehist_db.start_time = apply_date_patch(chargehist.get("charging_start", datetime.datetime(1970, 1, 1)))
            chargehist_db.end_time = apply_date_patch(chargehist.get("charging_end", datetime.datetime(1970, 1, 1)))
            chargehist_db.gids_start = chargehist.get("remaining_gids_at_start", 0)
            chargehist_db.gids_end = chargehist.get("remaining_gids_at_end", 0)
            chargehist_db.charge_bars_start = chargehist.get("remaining_charge_bars_at_start", 0)
            chargehist_db.charge_bars_end = chargehist.get("remaining_charge_bars_at_end", 0)
            chargehist_db.power_consumption = chargehist.get("power_consumption", 0)
            chargehist_db.charging_type = chargehist.get("charging_type", 1)
            chargehist_db.latitude = chargehist.get("lat", 0.0)
            chargehist_db.longitude = chargehist.get("lon", 0.0)
            chargehist_db.batt_avg_temp_start = chargehist.get("batt_avg_temp_start", 0)
            chargehist_db.batt_avg_temp_end = chargehist.get("batt_avg_temp_end", 0)
            chargehist_db.batt_max_temp_start = chargehist.get("batt_max_temp_start", 0)
            chargehist_db.batt_max_temp_end = chargehist.get("batt_max_temp_end", 0)
            chargehist_db.batt_min_temp_start = chargehist.get("batt_min_temp_start", 0)
            chargehist_db.batt_min_temp_end = chargehist.get("batt_min_temp_end", 0)
            chargehist_db.batt_avg_cell_volt_start = chargehist.get("batt_avg_cell_volt_start", 0)
            chargehist_db.batt_max_cell_volt_start = chargehist.get("batt_max_cell_volt_start", 0)
            chargehist_db.batt_min_cell_volt_start = chargehist.get("batt_min_cell_volt_start", 0)
            chargehist_db.current = chargehist.get("current_accumulation_start", 0)
            chargehist_db.charges_while_ignoff = chargehist.get("no_charges_while_ignoff", 0)
            chargehist_db.save()

    if "absdata" in crm_pload:
        for absdata in crm_pload["absdata"]:
            abs_db = CRMABSHistoryRecord()
            abs_db.car = car
            abs_db.timestamp = apply_date_patch(absdata.get("abs_operation_start_ts", datetime.datetime(1970, 1, 1)))
            abs_db.operation_time = absdata.get("operation_time", 0)
            abs_db.latitude = absdata.get("navi_pos_lat", 0.0)
            abs_db.longitude = absdata.get("navi_pos_lon", 0.0)
            abs_db.road_type = absdata.get("road_type", 0)
            abs_db.direction = absdata.get("navi_direction", 0)
            abs_db.vehicle_speed_start = absdata.get("vehicle_speed_at_start", 0)
            abs_db.vehicle_speed_end = absdata.get("vehicle_speed_at_end", 0)
            abs_db.save()

    if "trouble" in crm_pload:
        for troublerow in crm_pload["trouble"]:
            for trouble in troublerow:
                trouble_db = CRMTroubleRecord()
                trouble_db.car = car
                trouble_db.data = trouble
                trouble_db.save()

    if "distance" in crm_pload:
        for distance in crm_pload["distance"]:
            distance_db = CRMDistanceRecord()
            distance_db.car = car
            distance_db.timestamp = apply_date_patch(distance.get('timestamp', datetime.datetime(1970, 1, 1)))
            distance_db.consumed_wh = distance.get("consumed_wh", 0)
            distance_db.regenerated_wh = distance.get("regenerated_wh", 0)
            distance_db.latitude = distance.get("latitude", 0.0)
            distance_db.longitude = distance.get("longitude", 0.0)
            distance_db.road_type = distance.get("road_type", 0)
            distance_db.save()

    if "trips" in crm_pload:
        for trip in crm_pload["trips"]:
            trip_db = CRMTripRecord()
            trip_db.car = car
            trip_db.start_ts = apply_date_patch(trip.get("start", datetime.datetime(1970, 1, 1)))
            trip_db.end_ts = apply_date_patch(trip.get("stop", datetime.datetime(1970, 1, 1)))
            if "start_location" in trip:
                trip_db.start_latitude = trip["start_location"].get("lat", 0.0)
                trip_db.start_longitude = trip["start_location"].get("lon", 0.0)
            if "stop_location" in trip:
                trip_db.end_latitude = trip["stop_location"].get("lat", 0.0)
                trip_db.end_longitude = trip["stop_location"].get("lon", 0.0)
            trip_db.distance = trip.get("distance", 0.0)
            trip_db.sudden_accelerations = trip.get("sudden_accelerations", 0)
            trip_db.sudden_decelerations = trip.get("sudden_decelerations", 0)
            trip_db.highway_optimal_speed_time = trip.get("expressway_optional_speed_time", 0)
            trip_db.aircon_usage = trip.get("aircon_usage_time", 0)
            trip_db.highway_driving_time = trip.get("highway_driving_time", 0)
            trip_db.idling_time = trip.get("idling_time", 0)
            trip_db.average_speed = trip.get("average_speed", 0)
            trip_db.outside_temp_start = trip.get("outside_temp_start", 0)
            trip_db.outside_temp_end = trip.get("outside_temp_stop", 0)
            trip_db.trip_time = trip.get("time", 0)
            trip_db.regen = trip.get("regen", 0)
            trip_db.aircon_consumption = trip.get("aircon_consumption", 0)
            trip_db.auxiliary_consumption = trip.get("auxiliary_consumption", 0)
            trip_db.motor_consumption = trip.get("motor_consumption", 0)
            trip_db.headlight_on_time = trip.get("headlignt_on_time", 0)
            trip_db.average_acceleration = trip.get("average_accel", 0)
            trip_db.start_odometer = trip.get("start_odometer", 0)
            trip_db.max_speed = trip.get("max_speed", 0)
            if "accelerator_work" in trip:
                trip_db.sudden_start_consumption = trip["accelerator_work"].get("sudden_start_consumption", 0)
                trip_db.sudden_start_time = trip["accelerator_work"].get("sudden_start_time", 0)
                trip_db.sudden_acceleration_consumption = trip["accelerator_work"].get("sudden_acceleration_consumption", 0)
                trip_db.sudden_acceleration_time = trip["accelerator_work"].get("sudden_acceleration_time", 0)
                trip_db.non_eco_deceleration_consumption = trip["accelerator_work"].get("non_eco_deceleration_consumption", 0)
                trip_db.non_eco_deceleration_time = trip["accelerator_work"].get("non_eco_deceleration_time", 0)
            trip_db.idle_consumption = trip.get("idle_consumption", 0)
            trip_db.used_preheating = trip.get("used_preheating", False)
            trip_db.sudden_starts_list = json.dumps(trip.get("sudden_starts", []), default=str)
            trip_db.sudden_accelerations_list = json.dumps(trip.get("sudden_accelerations_list", []), default=str)
            trip_db.non_eco_decelerations_list = json.dumps(trip.get("non_eco_decelerations", []), default=str)
            trip_db.non_constant_speeds = json.dumps(trip.get("non_constant_speeds", []), default=str)
            if "batt_info" in trip:
                trip_db.batt_temp_start = trip["batt_info"].get("temp_start", 0)
                trip_db.batt_temp_stop = trip["batt_info"].get("temp_end", 0)
                trip_db.soh_start = trip["batt_info"].get("soh_start", 0)
                trip_db.soh_end = trip["batt_info"].get("soh_end", 0)
                trip_db.wh_energy_start = trip["batt_info"].get("wh_energy_start", 0)
                trip_db.wh_energy_end = trip["batt_info"].get("wh_energy_end", 0)
            if "batt_degradation_analysis" in trip:
                trip_db.bda_energy_content_start = trip["batt_degradation_analysis"].get("energy_content_start", 0)
                trip_db.bda_energy_content_end = trip["batt_degradation_analysis"].get("energy_content_end", 0)
                trip_db.bda_avg_temp_start = trip["batt_degradation_analysis"].get("avg_temp_start", 0)
                trip_db.bda_max_temp_start = trip["batt_degradation_analysis"].get("max_temp_start", 0)
                trip_db.bda_min_temp_start = trip["batt_degradation_analysis"].get("min_temp_start", 0)
                trip_db.bda_avg_temp_end = trip["batt_degradation_analysis"].get("avg_temp_end", 0)
                trip_db.bda_max_temp_end = trip["batt_degradation_analysis"].get("max_temp_end", 0)
                trip_db.bda_min_temp_end = trip["batt_degradation_analysis"].get("min_temp_end", 0)
                trip_db.bda_avg_cell_volt_start = trip["batt_degradation_analysis"].get("avg_cell_volt_start", 0)
                trip_db.bda_max_cell_volt_start = trip["batt_degradation_analysis"].get("max_cell_volt_start", 0)
                trip_db.bda_min_cell_volt_start = trip["batt_degradation_analysis"].get("min_cell_volt_end", 0)
                trip_db.bda_regen_end = trip["batt_degradation_analysis"].get("regen_end", 0)
                trip_db.bda_number_ac_charges = trip["batt_degradation_analysis"].get("number_ac_charges", 0)
                trip_db.bda_number_qc_charges = trip["batt_degradation_analysis"].get("number_qc_charges", 0)
                trip_db.bda_soc_end = trip["batt_degradation_analysis"].get("soc_end", 0)
                trip_db.resistance = trip["batt_degradation_analysis"].get("resistance_end", 0)
            trip_db.eco_tree_count = trip.get("eco_trees", 0)
            if "batt_degradation_analysis_new" in trip:
                trip_db.bda2_soc_end = trip["batt_degradation_analysis_new"].get("soc_end", 0)
                trip_db.bda2_capacity_bars_end = trip["batt_degradation_analysis_new"].get("capacity_bars_end", 0)
            trip_db.save()






