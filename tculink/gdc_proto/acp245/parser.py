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
    reason, li = _decode_ie_element(data, offset, li, IE_Element())

    return {
        "conversion_type": conversion_type.get("value"),
        "reason": reason.get("value"),
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