"""
New Probe methods, fields and functions for FICOSA TCUs.
A big part of Probe data has been made "backwards-compatible" to Nissan's old format.
New data fields have yet-to-be-determined data format and new IDs
"""

NEW_FIELDS = {
#   DataID -> desc(None=unknown)|length(incl. two bytes for DataID)
    0x101: (None, 0x12f), #dtchistory?
    0x103: (None, 0x522), #dtchistory_long?
    0x108: (None, 0x6d), #dtchistory_short
    0x109: (None, 0), #dtchistory_dynamic
    0x10a: (None, 0xe), #dtchistory_shortest
    0x10c: (None, 0xc5), #dtchistory_midsize
    0x10f: (None, 0x100), #dtchistory_x100
    0x110: (None, 3),
    0x111: (None, 6),
    0x112: (None, 4), # possible angle or heading? UINT is divided by 360000 and then cast to short.
    0x113: (None, 4),
    0x114: (None, 4),
    0x115: (None, 4),
    0x116: (None, 4),
    0x117: (None, 0x30),
    0x118: (None, 0x30),
    0x11a: (None, 0x2a),
    0x11b: (None, 4),
    0x11c: (None, 4),
    0x11e: (None, 0x30),
    0x11f: (None, 0x2a),
    0x120: (None, 0x2a),
    0x121: (None, 0x10),
    0x122: (None, 6),
    0x123: (None, 6),
    0x124: (None, 4),
    0x125: (None, 6),
    0x126: (None, 0x11),
    0x127: ("driving_scores", 6), # byte0 = ecoscore, byte1 = start score, byte2 = cruise score, byte 3 = slowdown score,
    0x128: ("tpms_data", 8), # byte0 = FR, byte1 = FL, byte2 = RR, byte3 = RL, byte4 = Front Setting Value (normal pressure value?), byte5 = Rear Setting Value (normal pressure value?)
    0x134: ("gids_when_new", 4), # number of gids when new
    0x135: ("trip_counter", 3) # Number of trips, aka. car start-ups. Resets to 0 after 0xFF/255, max value.
}

def make_crm_parsing_block_v2(data_id, data_bin) -> dict|None:
    if data_id not in NEW_FIELDS or NEW_FIELDS[data_id][0] is None:
        return None
    new_block = {"type": data_id, "struct": "", "data": bytearray(), "ficosa": {}}

    if data_id == 0x127:
        new_block["struct"] = "trips"
        new_block["ficosa"]["new_eco_score"] = data_bin[0]
        new_block["ficosa"]["start_score"] = data_bin[1]
        new_block["ficosa"]["cruise_score"] = data_bin[2]
        new_block["ficosa"]["slowdown_score"] = data_bin[3]

    if data_id == 0x128:
        new_block["struct"] = "trips"
        new_block["ficosa"]["tpms"] = {
            "fr": data_bin[0],
            "fl": data_bin[1],
            "rr": data_bin[2],
            "rl": data_bin[3],
            "front_setting": data_bin[4],
            "rear_setting": data_bin[5],
        }

    if data_id == 0x134:
        new_block["struct"] = "trips"
        new_block["ficosa"]["gids_when_new"] = int.from_bytes(data_bin, byteorder="big")

    if data_id == 0x135:
        new_block["struct"] = "trips"
        new_block["ficosa"]["trips"] = data_bin[0]

    return new_block