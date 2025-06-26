
def get_packet_type(first_byte):
    if first_byte == 0x01:
        return 1, "INIT"
    if first_byte == 0x03:
        return 3, "DATA"
    if first_byte == 0x05:
        return 5, "CONFIG"
    return -1, "UNKNOWN"

# In type 1 and type 2, 100th byte
def get_body_type(byte):
    if byte == 0x27:
        return "logon"
    if byte == 0x29:
        return "cp_remind"
    if byte == 0x2c:
        return "ac_result"
    if byte == 0x28:
        return "charge_status"
    if byte == 0x2a:
        return "remote_stop"
    if byte == 0x2b:
        return "charge_result"
    if byte == 0x2e:
        return "config_read"
    return None

def check_packet_size_match(packet):
    if len(packet) < 5:
        return False
    data_type = get_packet_type(packet[0])
    if data_type[0] == -1:
        return False
    if data_type[1] == 5:
        return len(packet) == 597 and packet[2] == 0x02

    size_byte = int(packet[3])
    return size_byte == len(packet)

def parse_tcu_info(packet):
    if len(packet) < 100:
        return None

    veh_ids = packet[4:]
    return {
        "vehicle_descriptor": packet[1],
        "vehicle_code1": veh_ids[0],
        "vehicle_code2": veh_ids[1],
        "vehicle_code3": veh_ids[2],
        "vehicle_code4": veh_ids[3],
        "vin": veh_ids[5:22].decode('ascii').rstrip('\x00').strip(),
        "tcu_id": veh_ids[23:35].decode('ascii').rstrip('\x00').strip(),
        "msn": veh_ids[36:51].decode('ascii').rstrip('\x00').strip(),
        "unit_id": veh_ids[52:64].decode('ascii').rstrip('\x00').strip(),
        "iccid": veh_ids[65:85].decode('ascii').rstrip('\x00').strip(),
        "sw_version": veh_ids[86:95].decode('ascii').rstrip('\x00').strip()
    }

def parse_auth_info(packet):
    if len(packet) < 34:
        return None
    return {
        "user": packet[1:16].decode('ascii').rstrip('\x00').strip(),
        "pass": packet[18:33].decode('ascii').rstrip('\x00').strip(),
    }

def parse_environment_info(packet):
    if len(packet) < 19:
        return {
            "gps": None
        }
    return {
        "gps": parse_gps_info(packet[3:16])
    }

def extract_aconrange(byte1, byte2):
    extracted = ((byte1 >> 3) & 0b11111)  # Extract bits 3-7 from byte1
    extracted = (extracted << 2) | ((byte2 >> 6) & 0b11)  # Add bits 0-1 from byte2
    return extracted  # Returns an integer

def bitstring_to_bytes(s):
    v = int(s, 2)
    b = bytearray()
    while v:
        b.append(v & 0xff)
        v >>= 8
    return bytes(b[::-1])

# Dirty solution but so be it :)
def extract_acon(byte1, byte2):
    bin1 = f"{byte1:08b}"
    bin2 = f"{byte2:08b}"

    highlighted = bin1[2:8] + bin2[:1]
    return bitstring_to_bytes(highlighted)[0]


def extract_soc(binary):
    mask = 0b111111
    masked = binary & mask
    result = masked << 1
    return result

def parse_evinfo(byte_data, aze0=False):
    rangeinfo_len = int(byte_data[0])

    evinfo_len = int(byte_data[8])

    # AC & DC charge state
    charge_state = (byte_data[9] >> 6) & 0b11

    pluggedin = (byte_data[9] & 1) == 1
    charging = charge_state == 1
    acstate = bool((byte_data[9] >> 1) & 0b1)
    quick_charging = charge_state == 2

    charge_finished = False

    if charge_state == 3:
        # When data indicates both QC and AC charge, it means charge finished.
        charge_finished = True
        charging = False
        quick_charging = False

    chg_time_1 = (
        (byte_data[10] << 3) | ((byte_data[11] & 0b11100000) >> 5)
    )

    chg_time_2 = (
        ((byte_data[11] & 0b00011111) << 6) | ((byte_data[12] & 0b11111100) >> 2)
    )

    chg_time_3 = 0xFFF

    # Drive info
    # GEAR info, True = D, False = R or N?
    drive_forward = bool(byte_data[9] & 0b00001000)
    park_gear = bool(byte_data[9] & 0b00000100)
    ignition = bool(byte_data[9] & 0b00100000)


    # Battery info
    soc_display = 0
    chargebars = (
        ((byte_data[18] & 0b00000011) << 2) | ((byte_data[19] & 0b11000000) >> 6)
    )
    capacity_bars = (byte_data[19] & 0b00011110) >> 1
    byte1 = byte_data[16]  # 01010001 in binary
    byte2 = byte_data[17]  # 00100000 in binary

    soc = (
            ((byte1 & 0b01111111) << 4) | ((byte2 & 0b11110000) >> 4)
    )
    soc = soc / 20
    gids = (
        ((byte_data[14] & 0b11111111) << 2) | ((byte_data[15] & 0b11000000) >> 6)
    )
    soh = (
        ((byte_data[15] & 0b00111111) << 1) | ((byte_data[16] & 0b10000000) >> 7)
    )

    param21 = 0

    counter = (
        ((byte_data[12] & 0b00000011) << 8) | (byte_data[13])
    )

    if aze0:
        chg_time_3 = (
            (byte_data[20] << 3) | ((byte_data[21] & 0b11100000) >> 5)
        )

        param21 = (byte_data[21] & 0b00011111)


    range_acon = byte_data[2]
    range_acoff = byte_data[4]

    resultstate = byte_data[7]
    alertstate = byte_data[6]

    return {
        "rangeinfo_len": rangeinfo_len,
        "evinfo_len": evinfo_len,
        "acon": range_acon,
        "acoff": range_acoff,
        "pluggedin":pluggedin,
        "charging": charging,
        "quick_charging": quick_charging,
        "charging_finish": charge_finished,
        "acstate": acstate,
        "chargebars": chargebars,
        "chargestate": charge_state,
        "resultstate": resultstate,
        "alertstate": alertstate,
        "ignition": ignition,
        "parked": park_gear,
        "direction_forward": drive_forward,
        "soc": soc,
        "soc_display": soc_display,
        "gids": gids,
        "soh": soh,
        "counter": counter,
        "param21": param21,
        "capacity_bars": capacity_bars,
        "full_chg": chg_time_1,
        "limit_chg": chg_time_2,
        "6kw_chg": chg_time_3
    }

def parse_config_data(byte_data):
    if len(byte_data) < 495:
        print("Config data error! Input too short")
        return None

    dial_code = get_and_validate_conf_entry(byte_data[5:], True)
    apn_name = get_and_validate_conf_entry(byte_data[39:], True)
    apn_user = get_and_validate_conf_entry(byte_data[89:], True)
    apn_pass = get_and_validate_conf_entry(byte_data[123:], True)
    dns1 = get_and_validate_conf_entry(byte_data[157:], True)
    dns2 = get_and_validate_conf_entry(byte_data[191:], True)
    server_url = get_and_validate_conf_entry(byte_data[225:], True)
    proxy_url = get_and_validate_conf_entry(byte_data[355:], True)
    gprs_type = get_and_validate_conf_entry(byte_data[491:], True)

    return {
        "dial_code": dial_code,
        "apn_name": apn_name,
        "apn_user": apn_user,
        "apn_pass": apn_pass,
        "dns1": dns1,
        "dns2": dns2,
        "server_url": server_url,
        "proxy_url": proxy_url,
        "gprs_type": gprs_type,
    }



def get_and_validate_conf_entry(byte_data, decode_ascii=False):
    field_type = byte_data[0]
    length = 0
    start_pos = 1
    if field_type == 0x60:
        # Defined length
        length = int(byte_data[1])
        start_pos = 2
    elif field_type == 0x61:
        # 128-byte field
        length = 128
        start_pos = 2
    elif field_type == 0x45:
        length = 5
    elif field_type == 0x43:
        length = 3
    else:
        print("Unknown data field type", field_type)
        return None

    if len(byte_data) < length-start_pos:
        print("Config data field error! Input too short")
        return None

    config_value = byte_data[start_pos:length]
    if decode_ascii:
        return config_value.decode('ascii').rstrip('\x00')
    return config_value




def parse_gps_info(byte_data):
    if len(byte_data) < 14:
        print("Error: GPS data must be at least 14 bytes long (7-14 contain location data).")
        return None


    # Extract home (byte 6, 0-indexed 5)
    # Ensure home_byte is within 8-bit range (since it's effectively a byte)
    home_byte = byte_data[5] & 0xFF

    # Extract flags using bitwise operations
    pos_uint = (home_byte >> 7) & 1  # Bit 7: Position indicator
    uint_datum2 = (home_byte >> 6) & 1  # Bit 6: Datum flag
    lat_mode_uint = (home_byte >> 5) & 1  # Bit 5: Latitude mode
    longitude_mode_uint = (home_byte >> 4) & 1  # Bit 4: Longitude mode
    home_uint = (home_byte >> 3) & 1  # Bit 3: Home indicator

    # Interpret the flags
    position_status = pos_uint == 1
    datum_status = uint_datum2 == 1
    latitude_mode = "N" if lat_mode_uint == 0 else "S"
    longitude_mode = "E" if longitude_mode_uint == 0 else "W"
    home_status = home_uint == 0

    # Extract latitude (bytes 6-9, 0-indexed)
    lat_deg = byte_data[6]  # Byte 7
    lat_min = byte_data[7]  # Byte 8
    lat_sec = int.from_bytes(byte_data[8:10], byteorder='big')  # Bytes 9-10

    # Extract longitude (bytes 10-13, 0-indexed)
    lon_deg = byte_data[10]  # Byte 11
    lon_min = byte_data[11]  # Byte 12
    lon_sec = int.from_bytes(byte_data[12:14], byteorder='big')  # Bytes 13-14

    # Convert seconds (assuming scaling factor of 100)
    lat_sec_float = lat_sec / 100.0
    lon_sec_float = lon_sec / 100.0

    # Convert to decimal degrees
    latitude = lat_deg + (lat_min / 60.0) + (lat_sec_float / 3600.0)
    longitude = lon_deg + (lon_min / 60.0) + (lon_sec_float / 3600.0)

    # Apply coordinates based on latitude and longitude modes
    if latitude_mode == "S":
        latitude = -latitude
    if longitude_mode == "W":
        longitude = -longitude

    return {
        "valid_position": position_status,
        "latitude": latitude,
        "longitude": longitude,
        "lat_mode": latitude_mode,
        "lon_mode": longitude_mode,
        "home_status": home_status,
        "datum": datum_status,
    }

