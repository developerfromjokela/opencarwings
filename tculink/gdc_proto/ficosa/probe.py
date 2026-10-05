"""
New Probe methods, fields and functions for FICOSA TCUs.
A big part of Probe data has been made "backwards-compatible" to Nissan's old format.
New data fields have yet-to-be-determined data format and new IDs
"""
from tculink.gdc_proto.acp245.parser import decode_dtc_code, ECU_CAN_IDS

NEW_FIELDS = {
#   DataID -> desc(None=unknown)|length(incl. two bytes for DataID)
    # ---- ECU DTC Codes --------
    0x129: (0x7E8, 4), # ECU 7E8
    0x12a: (0x7E9, 4), # ECU 7E9
    0x12b: (0x765, 4), # ECU 765
    0x12d: (0x7ED, 4), # ECU 7ED
    0x12e: (0x7BB, 4), # ECU 7BB
    0x12f: (0x768, 4), # ECU 768
    0x130: (0x7BD, 4), # ECU 7BD
    0x131: (0x772, 4), # ECU 772
    0x132: (0x763, 4), # ECU 763
    # ---------------------------
    0x101: (None, 0x12f), # 0x7e0,0x7e8
    0x103: (None, 0x522), # 0x7e0,0x7e8, LIDs 0x1801, 0x1802, 0x1803, 0x1804, 0x1805, 0x1806, 0x1807, 0x1808, 0x1809, 0x180a, 0x180b, 0x1821, 0x1822, 0x1823, 0x1824, 0x1825, 0x1841, 0x1842, 0x1843, 0x1844, 0x1845, 0x1846, 0x1847, 0x1848, 0x1849, 0x184a, 0x184b, 0x184c, 0x1851, 0x1852, 0x1853, 0x1854, 0x1855, 0x1856, 0x1861, 0x1862, 0x1863
    0x108: (None, 0x6d), # 0x7e5,0x7ed LIDs 1-3
    0x109: (None, 0), # 0x79d,0x7bd, LIDs 1-6
    0x10a: (None, 0xe), # 0,0 LIDs 1-3
    0x10c: (None, 0xc5), # 0x748,0x768, LIDs 1-2
    0x10f: (None, 0x100), # 0x7e1, 0x7e9 LID 0
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

    if 0x129 <= data_id <= 0x132 and len(data_bin) % 4 == 0:
        new_block["struct"] = "trouble"
        dtcs = []
        ecu_id = NEW_FIELDS[data_id][0]
        for itm in range(len(data_bin) // 4):
            dtc_data = data_bin[itm * 4 : itm * 4 + 4]
            dtc_code = decode_dtc_code(dtc_data)
            dtcs.append({"ecu_id": ecu_id,
                         "ecu_label": ECU_CAN_IDS.get(ecu_id),
                         "code": int.from_bytes(dtc_data, "big"),
                         "code_label": dtc_code})
        new_block["ficosa"]["dtcs"] = dtcs

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