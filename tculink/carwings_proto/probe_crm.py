from db.models import Car
from tculink.carwings_proto.crm_labels import CRM_LABELS

from tculink.carwings_proto.utils import parse_std_location
import struct
import datetime

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
    "trouble": 0xF8
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
            print("Label: ", item_type, hex(item_type))
            print("Datafield type: ", meta["type"])
            if meta["type"] == 7:
                size_field = dotfile_data[pos + 1]
                print("Block count", size_field)
                size = 6 * size_field
                print("Size: ", hex(size))
                if size == 0:
                    size += 1
                size = size+2
            elif meta["type"] == 0x10:
                size_field = dotfile_data[pos + 7]
                print("MSN Byte count", size_field)
                print("Size: ", hex(size))
                if size == 0:
                    size += 1
                size = size+8
            elif meta["type"] == 0x11:
                size_field = dotfile_data[pos + 1]
                print("Block count", size_field)
                size = 0x20 * size_field
                print("Size: ", hex(size))
                if size == 0:
                    size += 1
                size = size+2
            elif meta["type"] == 0x12 or meta["type"] == 0x13\
                    or meta["type"] == 0x14 or meta["type"] == 0x15:
                size_field = dotfile_data[pos + 1]
                print("Block count", size_field)
                size = 20 * size_field
                print("Size: ", hex(size))
                if size == 0:
                    size += 1
                size = size+2
            elif meta["type"] == 0x17:
                size_field = dotfile_data[pos + 1]
                print("Block count", size_field)
                size = 25 * size_field
                print("Size: ", hex(size))
                if size == 0:
                    size += 1
                size = size+2
            print("DATALEN:",size-1)
            orig_buf_offset = int(meta["a2"], 16) - int(meta["a1"], 16)
            parsingblocks.append({
                "type": item_type,
                "struct": sections[meta["structure"]],
                "data": dotfile_data[pos + 1:pos + size],
                "a1": meta["a1"],
                "a2": meta["a2"],
                "a3": meta["a3"],
                "offset": orig_buf_offset,
            })
            # advance one byte if empty
            if size == 0:
                pos += 1
            else:
                pos += size
            print("-------------------")
        else:
            raise Exception("UNKNOWN TYPE: ",item_type,"HEX", hex(item_type), "pos:",pos)

    print("-- Start parsing crmblocks --")

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
        "trouble": []
    }

    currentblock = None
    draft_struct = {}

    for crmblock in parsingblocks:
        if currentblock is None:
            print("Starting to parse crmblock ", crmblock["struct"])
            currentblock = crmblock["struct"]
        elif currentblock != crmblock["struct"]:
            print("Block change, closing block", currentblock)
            if isinstance(parse_result[currentblock], dict):
                parse_result[currentblock] = draft_struct
            else:
                parse_result[currentblock].append(draft_struct)
            draft_struct = {}
            currentblock = crmblock["struct"]
        elif crmblock["type"] in list(first_blocks.values()):
            print("Identified head item! saving previous object and opening new")
            if len(draft_struct.keys()) > 0:
                if isinstance(parse_result[currentblock], dict):
                    parse_result[currentblock] = draft_struct
                else:
                    parse_result[currentblock].append(draft_struct)
            draft_struct = {}
            currentblock = crmblock["struct"]

        print("Block ", crmblock["type"])
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
            draft_struct["start"] = datetime.datetime(2000 + block_data[0], block_data[1], block_data[2])
            continue
        if crmblock["type"] == 0xA1:
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
                print("WARN! mismatch block size")
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
                print("WARN! mismatch block size")
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
            location = parse_std_location(int.from_bytes(block_data[1:5], "big"), int.from_bytes(block_data[5:9], "big"))
            draft_struct["start_location"] = {"lat": location[0], "lon": location[1], "raw": hex(block_data)}
            continue
        if crmblock["type"] == 0x83:
            location = parse_std_location(int.from_bytes(block_data[1:5], "big"), int.from_bytes(block_data[5:9], "big"))
            draft_struct["stop_location"] = {"lat": location[0], "lon": location[1], "raw": hex(block_data)}
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
            draft_struct["outside_temp_start"] = int.from_bytes(block_data, byteorder="big", signed=False)
            continue
        if crmblock["type"] == 0x91:
            draft_struct["outside_temp_stop"] = int.from_bytes(block_data, byteorder="big", signed=False)
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
            for i in range(items_count+1):
                item_data = block_data[(i*20)+1:((i+1)*20)+1]
                location = parse_std_location(int.from_bytes(block_data[12:16], "big"), int.from_bytes(block_data[16:20], "big"))
                sudden_starts.append({
                    "timestamp": datetime.time(item_data[0], block_data[1], block_data[2], block_data[3]),
                    "power_consumption": block_data[4:8],
                    "elapsed_time": block_data[8:12],
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["sudden_starts"] = sudden_starts
            continue
        if crmblock["type"] == 0xD4:
            sudden_accels = []
            items_count = block_data[0]
            for i in range(items_count+1):
                item_data = block_data[(i*20)+1:((i+1)*20)+1]
                location = parse_std_location(int.from_bytes(block_data[12:16], "big"), int.from_bytes(block_data[16:20], "big"))
                sudden_accels.append({
                    "timestamp": datetime.time(item_data[0], block_data[1], block_data[2], block_data[3]),
                    "power_consumption": block_data[4:8],
                    "elapsed_time": block_data[8:12],
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["sudden_accelerations"] = sudden_accels
            continue
        if crmblock["type"] == 0xD5:
            non_eco_decelerations = []
            items_count = block_data[0]
            for i in range(items_count+1):
                item_data = block_data[(i*20)+1:((i+1)*20)+1]
                location = parse_std_location(int.from_bytes(block_data[12:16], "big"), int.from_bytes(block_data[16:20], "big"))
                non_eco_decelerations.append({
                    "timestamp": datetime.time(item_data[0], block_data[1], block_data[2], block_data[3]),
                    "power_consumption": block_data[4:8],
                    "elapsed_time": block_data[8:12],
                    "latitude": location[0],
                    "longitude": location[1],
                })
            draft_struct["non_eco_decelerations"] = non_eco_decelerations
            continue
        if crmblock["type"] == 0xD6:
            non_constant_speeds = []
            items_count = block_data[0]
            for i in range(items_count+1):
                item_data = block_data[(i*20)+1:((i+1)*20)+1]
                location = parse_std_location(int.from_bytes(block_data[12:16], "big"), int.from_bytes(block_data[16:20], "big"))
                non_constant_speeds.append({
                    "timestamp": datetime.time(item_data[0], block_data[1], block_data[2], block_data[3]),
                    "power_consumption": block_data[4:8],
                    "elapsed_time": block_data[8:12],
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
                "capacity_bars_end": block_data[0],
                "soc_end": block_data[1],
            }
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
            charges = []
            for i in range(items_count+1):
                location = parse_std_location(int.from_bytes(block_data[:4], "big"), int.from_bytes(block_data[4:8], "big"))
                charger_loc = parse_std_location(int.from_bytes(block_data[22:26], "big"),int.from_bytes(block_data[26:30], "big"))
                charges.append({
                    "lat": location[0],
                    "long": location[1],
                    "charge_count": block_data[8],
                    "charge_type": block_data[9],
                    "start_ts": datetime.datetime(2000 + block_data[10], block_data[11], block_data[12], block_data[13],
                                                      block_data[14], block_data[15]),
                    "end_ts": datetime.datetime(2000 + block_data[16], block_data[17], block_data[18], block_data[19],
                                                      block_data[20], block_data[21]),
                    "charger_position_lat": charger_loc[0],
                    "charger_position_long": charger_loc[1],
                    "charger_position_flag": int.from_bytes(block_data[30:32], byteorder="big", signed=False)
                })
            draft_struct["charges"] = charges
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
            location = parse_std_location(int.from_bytes(block_data[21:25], "big"), int.from_bytes(block_data[25:29], "big"))
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
            offset = 1


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

                offset += 25
            draft_struct["records"] = records


        print("  -> Unknown")
        draft_struct[hex(crmblock["type"])] = crmblock["data"].hex()

    # insert last block if available
    if len(draft_struct.keys()) > 0:
        if isinstance(parse_result[currentblock], dict):
            parse_result[currentblock] = draft_struct
        else:
            parse_result[currentblock].append(draft_struct)

    return parse_result


# TODO
def update_crm_to_db(car: Car, crm_pload):
    ...