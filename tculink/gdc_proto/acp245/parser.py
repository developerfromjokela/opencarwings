from typing import Optional, Tuple, Dict, Any
from enum import Enum
from datetime import datetime

class ACPParseError(Exception):
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self):
        return f"ACPParseError({self.message!r}, code={self.code})"


def _need(data: bytes, offset: int, n: int, where: str):
    """
    Sanity check while reading data
    """
    if offset < 0 or offset + n > len(data):
        raise ACPParseError(f"{where}: truncated data (need {n} bytes at offset {offset}, "
                             f"have {len(data) - offset if offset <= len(data) else 0})")



def decode_app_header(data: bytes, offset: int) -> Tuple[Dict[str, Any], int]:
    if data is None:
        raise ACPParseError("AppHeader: null buffer")

    result: Dict[str, Any] = {}
    _need(data, offset, 2, "AppHeader")

    b0 = data[offset]

    # FICOSA uses to identify manufacturer specific packets
    result["special_flag"] = (b0 & 0b10000000) >> 7

    result["app_id"] = b0 & 0b00111111

    # non-standard flag (defined in protocol specification of ACP245)
    private_flag = 1 if (b0 & 0x40) else 0
    result["private_flag"] = private_flag
    if private_flag != 0:
        raise ACPParseError("AppHeader: Invalid Private Flag", code=1001)

    test_flag = 1 if (b0 & 0x20) else 0
    result["test_flag"] = test_flag
    if test_flag != 0:
        raise ACPParseError("AppHeader: Invalid Test Flag", code=1002)

    b1 = data[offset + 1]

    version_flag = 1 if (b1 & 0x80) else 0
    result["version_flag"] = version_flag
    if version_flag != 0:
        raise ACPParseError("AppHeader: Invalid Version Flag Nissan Extension", code=1003)

    nissan_ext_version = (b1 & 0x70) >> 4
    result["nissan_ext_version"] = nissan_ext_version
    if nissan_ext_version != 0:
        raise ACPParseError("AppHeader: Invalid Version Nissan Extension", code=1004)

    mcf = b1 & 0x0f
    result["mcf"] = mcf

    if mcf & 0x08:
        raise ACPParseError("AppHeader: Invalid MCF (bit3 set)", code=1005)

    if mcf & 0x04:
        _need(data, offset, 5, "AppHeader")
        result["length"] = int.from_bytes(
            bytes([data[offset + 4], data[offset + 2], data[offset + 3]]),
            byteorder="big"
        )
        consumed = 5
    elif mcf & 0x02:
        _need(data, offset, 4, "AppHeader")
        result["length"] = int.from_bytes(
            data[offset + 2:offset + 4],
            byteorder="big"
        )
        consumed = 4
    else:
        raise ACPParseError("AppHeader: Invalid MCF (neither bit1 nor bit2 set)", code=1006)

    return result, consumed


def parse_version_ficosa(data: bytes, offset: int) -> Tuple[Dict[str, Any], int]:
    """Decodes the FICOSA Version IE"""
    result: Dict[str, Any] = {}
    _need(data, offset, 1, "Version")

    b0 = data[offset]

    ie_id = b0 >> 6
    if ie_id != 0:
        raise ACPParseError("Version: Invalid IE ID", code=1011)

    more_flag = 1 if (b0 & 0x20) else 0
    if more_flag != 0:
        raise ACPParseError("Version: Invalid More Flag", code=1012)

    length = b0 & 0x1f
    if length != 4:
        raise ACPParseError("Version: Invalid Length", code=1013)

    _need(data, offset, 5, "Version")
    result["sw_version"] = data[offset + 1]
    result["hw_1"] = data[offset + 2]
    result["hw_2"] = data[offset + 3]
    result["hw_3"] = data[offset + 4]

    return result, 5


class IE_Element:
    class ElementType(Enum):
        UNCHECKED = -1
        BINARY = 0
        ASCII = 1
        PACKED_DECIMAL = 2
        RESERVED = 3
        UNICODE = 4
        UTF8 = 5
        SHIFT_JIS = 6
        # 7..30 reserved, 31 private (The value of 31 indicates that the element is not defined in this document
        # and is considered proprietary or private.)

    ie_id: ElementType = ElementType.UNCHECKED
    length: int = 0

    def __init__(self, ie_id: ElementType = ElementType.UNCHECKED.value, length: int = 0):
        self.ie_id = ie_id
        self.length = length

class VehDescElementInfo(Enum):
    VIN = IE_Element(1,  0x11)
    DCM_ID = IE_Element(1, 0x0c)
    IMEI_MSN = IE_Element(1, 0x0f)
    NAVI_ID = IE_Element(1, 0xc)
    SIM_ID = IE_Element(1, 0x14)
    DCM_VERSION = IE_Element(1, 10)
    BATT_ID = IE_Element(1, 0x20)
    VEHICLE_TYPE = IE_Element(1, 4)

def _decode_ie_element(data: bytes, p: int, li: int, ie_element: IE_Element, only_value=False) -> Tuple[Dict[str, Any]|str|bytes, int]:
    """
    Decode IE element, according to ACP 245 V1.2 protocol specifications.
    li tracks used up bytes, p is offset inside data argument
    """
    _need(data, p + li, 1, "VehDesc")
    b = data[p + li]

    if type(ie_element) == VehDescElementInfo:
        ie_element = ie_element.value

    ie_id = b >> 6
    if ie_id != ie_element.ie_id and ie_element.ie_id != -1:
        raise ACPParseError("VehDesc: Invalid IE ID", code=1021)

    more_flag = 1 if (b & 0x20) else 0

    length = b & 0x1f
    if more_flag == 1:
        b1 = data[p + li + 1]
        length = ((b & 0x1f) << 7) | (b1 & 0x7f)

    if length != ie_element.length and ie_element.length > 0:
        raise ACPParseError(f"VehDesc: Invalid Length, expected {ie_element.length}, got {length}", code=1022)

    _need(data, p + li + 1+more_flag, length, "VehDesc")
    raw = data[p + li + 1+more_flag: p + li + 1+more_flag + length]

    info = {
        "ie_id": ie_id,
        "more_flag": more_flag == 1,
        "length": length,
        "value": raw.decode("ascii", errors="replace").rstrip('\x00').strip()
                if ie_id == IE_Element.ElementType.ASCII.value else bytes(raw),
    }
    if only_value:
        return (raw.decode("ascii", errors="replace").rstrip('\x00').strip()
                if ie_id == IE_Element.ElementType.ASCII.value else bytes(raw)), li + 1+more_flag + length
    return info, li + 1+more_flag + length


def decode_veh_desc(data: bytes, offset: int) -> Tuple[Dict[str, Any], int]:
    """Decodes the ACP Vehicle Descriptor IE (VIN / DCM / IMEI-MSN / NAVI ID /
    SIM ID / DCM_VER / BATT ID / VEHICLE_TYPE)."""
    if data is None:
        raise ACPParseError("VehDesc: null buffer")

    result: Dict[str, Any] = {}
    p = offset
    _need(data, p, 1, "VehDesc")

    b0 = data[p]
    ie_id = b0 >> 6
    result["ie_id"] = ie_id
    if ie_id != 0:
        raise ACPParseError("VehDesc: Invalid IE ID", code=1031)

    more_flag = 1 if (b0 & 0x20) else 0
    result["more_flag"] = more_flag

    if more_flag == 0:
        length = b0 & 0x1f
        li = 1
        if length == 0:
            raise ACPParseError("VehDesc: Invalid Length", code=1032)
    else:
        _need(data, p, 2, "VehDesc")
        length = (b0 & 0x1f) << 7
        b1 = data[p + 1]
        length |= (b1 & 0x7f)
        if length < 0x20:
            raise ACPParseError("VehDesc: Invalid More Flag", code=1033)
        li = 2

    result["length"] = length

    _need(data, p + li, 1, "VehDesc")
    flags = data[p + li]
    result["flags"] = flags
    li += 1

    ext_flags = None
    if flags & 0x80:
        _need(data, p + li, 1, "VehDesc")
        ext_flags = data[p + li]
        result["ext_flags"] = ext_flags
        li += 1

    if flags & 0x20:
        result["vin"], li = _decode_ie_element(data, p, li, VehDescElementInfo.VIN, only_value=True)

    if flags & 0x10:
        result["dcm"], li = _decode_ie_element(data, p, li, VehDescElementInfo.DCM_ID, only_value=True)

    if flags & 0x01:
        result["imei_msn"], li = _decode_ie_element(data, p, li, VehDescElementInfo.IMEI_MSN, only_value=True)

    if flags & 0x80:
        # ext_flags sub-blocks (only reachable when the extended-flags byte was present)
        if ext_flags & 0x40:
            result["navi_id"], li = _decode_ie_element(data, p, li, VehDescElementInfo.NAVI_ID, only_value=True)

        if ext_flags & 0x20:
            result["sim_id"], li = _decode_ie_element(data, p, li, VehDescElementInfo.SIM_ID, only_value=True)

        if ext_flags & 0x10:
            result["dcm_ver"], li = _decode_ie_element(data, p, li, VehDescElementInfo.DCM_VERSION, only_value=True)

        if ext_flags & 0x02:
            result["batt_id"], li = _decode_ie_element(data, p, li, VehDescElementInfo.BATT_ID, only_value=True)

        if ext_flags & 0x01:
            result["vehicle_type"], li = _decode_ie_element(data, p, li, VehDescElementInfo.VEHICLE_TYPE, only_value=True)

    # Final overall-length cross-check
    expected_extra = 1 if more_flag == 0 else 2
    if li - expected_extra != length:
        raise ACPParseError("VehDesc: Invalid Length", code=1)

    return result, li


def decode_timestamp(data: bytes, offset: int) -> Tuple[Any, int]:
    """Decodes the ACP Timestamp IE"""
    _need(data, offset, 5, "TimeStamp")

    b0 = data[offset]

    ie_id = b0 >> 6
    if ie_id != 0:
        raise ACPParseError("TimeStamp: Invalid IE ID", code=1041)

    more_flag = 1 if (b0 & 0x20) else 0
    if more_flag != 0:
        raise ACPParseError("TimeStamp: Invalid More Flag", code=1042)

    length = b0 & 0x1f
    if length != 4:
        raise ACPParseError("TimeStamp: Invalid Length", code=1043)

    b1 = data[offset + 1]
    year = (b1 >> 2) + 1990
    if year >= 0x805:
        raise ACPParseError("TimeStamp: Invalid Year", code=1044)

    b2 = data[offset + 2]
    month = ((b1 & 0x03) << 2) | (b2 >> 6)
    if not (1 <= month <= 12):
        raise ACPParseError("TimeStamp: Invalid Month", code=1045)

    day = (b2 & 0x3e) >> 1
    if not (1 <= day <= 31):
        raise ACPParseError("TimeStamp: Invalid Day", code=1046)

    b3 = data[offset + 3]
    hour = ((b2 & 0x01) << 4) | (b3 >> 4)
    if hour >= 24:
        raise ACPParseError("TimeStamp: Invalid Hour", code=1047)

    b4 = data[offset + 4]
    minute = ((b3 & 0x0f) << 2) | (b4 >> 6)
    if minute >= 60:
        raise ACPParseError("TimeStamp: Invalid Minutes", code=1048)

    second = b4 & 0x3f
    if second >= 60:
        raise ACPParseError("TimeStamp: Invalid Seconds", code=1049)

    return datetime(year, month, day, hour, minute, second), 5

def get_single_byte(data: bytes, offset: int) -> int:
    _need(data, offset, 1, "SingleByte")
    return data[offset]

def decode_acp_auth(data: bytes, offset: int) -> Tuple[dict, int]:
    auth_data, all_li = _decode_ie_element(data, offset, 0, IE_Element())
    auth_data = auth_data["value"]
    username, li = _decode_ie_element(auth_data, 0, 0, IE_Element())
    password, li = _decode_ie_element(auth_data, 0, li, IE_Element())
    return {"username": username["value"], "password": password["value"]}, all_li

def decode_gps_position(data: bytes, offset: int) -> Tuple[dict, int]:
    byte_data, li = _decode_ie_element(data, offset, 0, IE_Element())
    byte_data = byte_data["value"]

    if len(byte_data) < 9:
        raise ACPParseError("GPS Position: Invalid Length", code=1030)

    # Extract home (byte 6, 0-indexed 5)
    # Ensure home_byte is within 8-bit range (since it's effectively a byte)
    home_byte = byte_data[0] & 0xFF

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

    lat_deg = byte_data[1]  # Byte 7
    lat_min = byte_data[2]  # Byte 8
    lat_sec = int.from_bytes(byte_data[3:5], byteorder='big')  # Bytes 9-10

    lon_deg = byte_data[5]  # Byte 11
    lon_min = byte_data[6]  # Byte 12
    lon_sec = int.from_bytes(byte_data[7:9], byteorder='big')  # Bytes 13-14

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
    }, li


def parse_ficosa_app_info(data: bytes, offset: int) -> Tuple[dict, int]:
    d, all_li = _decode_ie_element(data, offset, 0, IE_Element(length=8))
    data = d["value"]

    B = data[0]
    flags = {
        "fail": (B >> 5) & 0x7,  # 3 bits
        "acFinish": (B >> 4) & 0x1,  # 1 bit
        "chargeFinish": (B >> 1) & 0x7,  # 3 bits
        "plugReminder2": B & 0x1,  # 1 bit
    }

    # --- byte i2 + i3(top2): result bytes 0-3 (partial, low bits only) ---
    B2 = data[1]
    B3 = data[2]
    result = {
        "gba": (B2 >> 6) & 0x3,  # low 2 bits of result byte0
        "acResult": (B2 >> 3) & 0x7,  # low 3 bits of result byte1
        "chargeStop": (B2 >> 1) & 0x3,  # low 2 bits of result byte2
        "chargeStart": (B3 >> 6) & 0x3,  # low 2 bits of result byte3
    }

    # --- byte i3 + i4(top2): itm2 bytes 0-3 (partial) ---
    B4 = data[3]
    itm2 = {
        "acAutoOff": (B3 >> 4) & 0x3,  # low 2 bits
        "acOn": (B3 >> 2) & 0x3,  # low 2 bits
        "acOff": (B3 >> 1) & 0x1,  # low 1 bit
        "battInfo": (B4 >> 6) & 0x3,  # low 2 bits
    }

    # --- byte i4 + i5(top2): itm3 bytes 0-3 (partial) ---
    B5 = data[4]
    itm3 = {
        "timer": (B4 >> 4) & 0x3,  # low 2 bits
        "1": (B4 >> 1) & 0x7,  # low 3 bits
        "2": (B5 >> 6) & 0x3,  # low 2 bits
        "unblockCharge": (B5 >> 4) & 0x3,  # low 2 bits
    }

    # --- byte i5 + i6(top2): itm4 bytes 0-3 (partial) ---
    B6 = data[5]
    itm4 = {
        "blockChargeError": (B5 >> 2) & 0x3,  # low 2 bits
        "blockChargeResult": B5 & 0x3,  # low 2 bits
        "2": (B6 >> 6) & 0x3,  # low 2 bits
        "3": (B6 >> 4) & 0x3,  # low 2 bits
    }

    # --- byte i6 + i7 + i8: heatresult bytes 0-3 (partial) ---
    B7 = data[6]
    B8 = data[7]
    heatresult = {
        "batteryHeat": (B6 >> 2) & 0x3,  # low 2 bits
        "1": (B7 >> 5) & 0x7,  # low 3 bits
        "2": (B7 >> 2) & 0x7,  # low 3 bits
        "3": (B8 >> 5) & 0x7,  # low 3 bits
    }

    # --- byte i8: check ---
    check = (B8 >> 2) & 0x7  # low 3 bits

    return {
        "flags": flags,
        "result": result,
        "itm2": itm2,
        "itm3": itm3,
        "itm4": itm4,
        "heatresult": heatresult,
        "check": check,
        "raw": data
    }, all_li

def decode_ficosa_vehicle_security_header(data: bytes, offset: int) -> Tuple[dict, int]:
    return {
        "ver": int.from_bytes(data[offset:offset + 1], byteorder='big'),
        "p2": data[offset+2]
    }, 3

def decode_ficosa_vehicle_security_data(data: bytes, offset: int) -> Tuple[dict, int]:
    d, all_li = _decode_ie_element(data, offset, 0, IE_Element(length=7))
    data = d["value"]

    p3_mid = data[4]  # (p3 >> 8) & 0xFF
    p3_low = data[5]  # p3 & 0xFF
    opCode = data[6]  # (p3 >> 16) & 0xFF

    p3 = (opCode << 16) | (p3_mid << 8) | p3_low

    return {
        "code":  data[0],
        "type": data[2],
        "p5": data[3],
        "p3": p3
    }, all_li

def decode_probe_header(data: bytes, offset: int) -> Tuple[dict, int]:
    li = 0

    conversion_type, li = _decode_ie_element(data, offset, li, IE_Element())
    data_type, li = _decode_ie_element(data, offset, li, IE_Element())

    return {
        "conversion_type": conversion_type.get("value"),
        "data_type": data_type.get("value"),
    }, li


def decode_probe_data(data: bytes, offset: int) -> Tuple[dict, int]:
    probe_data, li = _decode_ie_element(data, offset, 0, IE_Element())

    probe_data = probe_data.get("value")

    if probe_data is None or len(probe_data) == 0:
        raise ACPParseError("Probe Data: Invalid Length")

    return {
        "type": probe_data[0],
        "data": probe_data[1:],
    }, li

def decode_probe_form_item(data: bytes, offset: int) -> Tuple[dict, int]:
    first_byte = data[offset] >> 7
    if first_byte != 1:
        raise ACPParseError("Probe Form: Invalid First Byte")

    li = 0

    element_id = data[offset + 1]
    length = data[offset + 2]
    li += 3
    if (length >> 7) == 1:
        # Extended length
        length_1 = data[offset + 2] & 0x7F
        length_2 = data[offset + 3]
        length = (length_1 << 8) | length_2
        li += 1
    element_data = data[offset + li:offset + li + length]
    li += length

    return {
        "id": element_id,
        "length": length,
        "data": element_data,
    }, li

def decode_record(record: bytes) -> dict:
    if len(record) != 3:
        raise ValueError(f"record must be exactly 3 bytes, got {record!r}")
    return {
        "tag": record[0],
        "status": record[1],
        "req_type": record[2],
    }


def decode_acp_config_results(buf, offset=0) -> Tuple[dict, int]:
    data_val, offset = _decode_ie_element(buf, offset, 0, IE_Element())
    count2 = data_val["length"]
    data_buf = data_val["value"]

    count = count2 >> 1
    values, triples = [], []
    pos = 0
    for _ in range(count):
        lo, hi = data_buf[pos], data_buf[pos + 1]
        pos += 2
        v = lo | ((hi >> 7 & 1) << 8) | ((hi >> 4 & 7) << 9)
        values.append(v)
        triples.append((v & 0xFF, (v >> 8) & 1, (v >> 9) & 7))
    return {
        "count": count,
        "configs": values,
        "triples": triples
    }, offset

DTC_STATUS_BIT_NAMES = {
    0: "testFailed",
    1: "testFailedThisOperationCycle",
    2: "pendingDTC",
    3: "confirmedDTC",
    4: "testNotCompletedSinceLastClear",
    5: "testFailedSinceLastClear",
    6: "testNotCompletedThisOperationCycle",
    7: "warningIndicatorRequested",
}

ECU_CAN_IDS = {
    0x70F: "BRAKE",
    0x760: "ABS",
    0x761: "VSP",
    0x762: "EPS",
    0x763: "METER",
    0x764: "HVAC",
    0x765: "BCM",
    0x767: "MULTI A/V",
    0x76D: "IPDM E/R",
    0x772: "AIRBAG",
    0x775: "PARKING BRAKE",
    0x778: "AVM",
    0x783: "TCU",
    0x78C: "MOTOR CONTROL",
    0x793: "CHARGER",
    0x79A: "EV/HEV",
    0x7BA: "AVM",
    0x7BB: "HV BATTERY",
    0x7BD: "SHIFT",

    0x740: "ABS",
    0x752: "AIBAG",
    0x745: "BCM",
    0x70E: "BRAKE",
    0x792: "CHARGER",
    0x755: "EHS/PKB",
    0x742: "EPS",
    0x797: "EV/HEV",
    0x79B: "HV Battery",
    0x744: "HVAC",
    0x74D: "IPDM E/R",
    0x743: "M&A",
    0x784: "MOTOR CONTROL",
    0x747: "MULTI A/V",
    0x79D: "SHIFT",
    0x746: "TCU",
    0x73F: "VSP",
    0x7B7: "AVM",
}

LETTER_MAP = {
    0b00: "P",  # Powertrain
    0b01: "C",  # Chassis
    0b10: "B",  # Body
    0b11: "U",  # Network/Communication
}

def decode_ficosa_dtc_info(buffer, offset=0) -> Tuple[dict, int]:

    def decode_dtc_code(code_bytes):
        b1 = code_bytes[0]
        b2 = code_bytes[1]
        b3 = code_bytes[2]
        b4 = -1
        if len(code_bytes) > 3:
            b4 = code_bytes[3]

        letter_bits = (b1 >> 6) & 0b11
        category_bits = (b2 >> 4) & 0b11

        letter = LETTER_MAP[letter_bits]

        prefix_digit = str(category_bits)
        code_number = f"{b1 & 0x0F:X}{b2:02X}"
        full_code = f"{letter}{prefix_digit}{code_number}"
        full_string = f"{full_code}-{b3:02X}"
        if b4 != -1:
            full_string += f"-{b4:02X}"
        return full_string

    data_val, data_offset = _decode_ie_element(buffer, offset, 0, IE_Element())
    data_val = data_val["value"]

    offset = 0

    tstamp_data = bytes([0x04])
    tstamp_data += data_val[:4]

    timestamp, _ = decode_timestamp(tstamp_data, 0)
    offset += 4

    long_count = data_val[offset]
    offset += 1

    dtc_long = []
    if 0 < long_count < 0xFF:
        for i in range(long_count):
            chunk = data_val[offset:offset + 9]
            ecu_id = int.from_bytes(chunk[0:4], "big")
            code = int.from_bytes(chunk[5:9], "big")
            flag = chunk[4]
            flags = {name: bool(flag & (1 << bit)) for bit, name in DTC_STATUS_BIT_NAMES.items()}
            dtc_long.append({"ecu_id": ecu_id, "ecu_label": ECU_CAN_IDS.get(ecu_id), "flags": flags, "flag_raw": flag,
                             "code": code, "code_label": decode_dtc_code(chunk[5:9])})
            offset += 9

    short_count = data_val[offset]
    offset += 1
    dtc_short = []
    if 0 < short_count < 0xFF:
        for i in range(short_count):
            chunk = data_val[offset:offset + 8]
            ecu_id = int.from_bytes(chunk[0:4], "big")
            code = int.from_bytes(chunk[5:8], "big")
            flag = chunk[4]
            flags = {name: bool(flag & (1 << bit)) for bit, name in DTC_STATUS_BIT_NAMES.items()}
            dtc_short.append({"ecu_id": ecu_id, "flags": flags, "flag_raw": flag, "code": code, "code_label": decode_dtc_code(chunk[5:8])})
            offset += 8

    return {
        "dtc_long": dtc_long,
        "dtc_short": dtc_short,
        "timestamp": timestamp,
    }, data_offset

def decode_ficosa_tire_pressure(buf, offset=0) -> Tuple[dict, int]:
    data_val, data_offset = _decode_ie_element(buf, offset, 0, IE_Element())
    data_val = data_val["value"]

    return {
        "light_status": data_val[0],
        "fr": data_val[1],
        "fl": data_val[2],
        "rr": data_val[3],
        "rl": data_val[4],
    }, data_offset

def decode_acp_maintenance_alert(buf, offset=0) -> Tuple[dict, int]:
    data_val, data_offset = _decode_ie_element(buf, offset, 0, IE_Element())
    data_val = data_val["value"]

    return {
        "alert_status": data_val[0],
        "mileage_km": int.from_bytes(data_val[1:], "big")
    }, data_offset