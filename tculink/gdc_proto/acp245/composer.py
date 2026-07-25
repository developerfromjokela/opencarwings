from datetime import datetime
from typing import Optional


def _encode_ie(value: str | bytes, ie_id=-1) -> bytes:
    if isinstance(value, str):
        raw = value.encode('ascii')
        if ie_id == -1:
            ie_id = 1
    else:
        raw = value
        if ie_id == -1:
            ie_id = 0
    length = len(raw)
    more = 1 if length > 0x1F else 0
    if more:
        b0 = (ie_id << 6) | (1 << 5) | (length >> 7) & 0x1F
        b1 = length & 0x7F
        return bytes([b0, b1]) + raw
    b0 = (ie_id << 6) | length
    return bytes([b0]) + raw

class ACPComposeError(Exception):
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.code = code


class AppHeader:
    def __init__(self, app_id: int = 0, mcf: int = 2, length: int = 0,
                 special_flag: int = 0, **kwargs):
        self.app_id = app_id & 0x3F
        self.mcf = mcf & 0x0F
        self.length = length
        self.special_flag = special_flag & 1
        self.private_flag = 0
        self.test_flag = 0
        self.version_flag = 0
        self.nissan_ext_version = 0

    def encode(self) -> bytes:
        if self.private_flag or self.test_flag or self.version_flag or self.nissan_ext_version:
            raise ACPComposeError("Invalid flags in AppHeader")
        if self.mcf & 0x08 or not (self.mcf & 0x06):
            raise ACPComposeError("Invalid MCF in AppHeader")

        b0 = (self.special_flag << 7) | (self.app_id & 0b01111111)
        b1 = self.mcf

        header = bytearray([b0, b1])

        self.length += 2
        if self.mcf & 0x04:  # 5-byte length
            len3 = self.length.to_bytes(3, 'big')
            self.length += 3
            header.extend([len3[0], len3[1], len3[2]])
        elif self.mcf & 0x02:  # 4-byte
            self.length += 2
            len2 = self.length.to_bytes(2, 'big')
            header.extend(len2)

        return bytes(header)


class VersionFicosa:
    def __init__(self, sw_version: int = 0, hw_1: int = 0, hw_2: int = 0, hw_3: int = 0):
        self.sw_version = sw_version & 0xFF
        self.hw_1 = hw_1 & 0xFF
        self.hw_2 = hw_2 & 0xFF
        self.hw_3 = hw_3 & 0xFF

    def encode(self) -> bytes:
        return _encode_ie(bytes([self.sw_version, self.hw_1, self.hw_2, self.hw_3]), ie_id=0)


class VehDesc:
    def __init__(self, **kwargs):
        self.vin = kwargs.get("vin")
        self.dcm = kwargs.get("dcm")
        self.imei_msn = kwargs.get("imei_msn")
        self.navi_id = kwargs.get("navi_id")
        self.sim_id = kwargs.get("sim_id")
        self.dcm_ver = kwargs.get("dcm_ver")
        self.batt_id = kwargs.get("batt_id")
        self.vehicle_type = kwargs.get("vehicle_type")

    def encode(self) -> bytes:
        flags = 0
        ext_flags = 0
        content = bytearray()

        if self.vin:
            flags |= 0x20
            content.extend(_encode_ie(self.vin))
        if self.dcm:
            flags |= 0x10
            content.extend(_encode_ie(self.dcm))
        if self.imei_msn:
            flags |= 0x01
            content.extend(_encode_ie(self.imei_msn))

        if self.navi_id:
            ext_flags |= 0x40
            content.extend(_encode_ie(self.navi_id))
        if self.sim_id:
            ext_flags |= 0x20
            content.extend(_encode_ie(self.sim_id))
        if self.dcm_ver:
            ext_flags |= 0x10
            content.extend(_encode_ie(self.dcm_ver))
        if self.batt_id:
            ext_flags |= 0x02
            content.extend(_encode_ie(self.batt_id))
        if self.vehicle_type:
            ext_flags |= 0x01
            content.extend(_encode_ie(self.vehicle_type))

        if ext_flags:
            flags |= 0x80

        result = bytearray([flags])
        if ext_flags:
            result.append(ext_flags)
        result.extend(content)
        return _encode_ie(result, ie_id=0)


class Timestamp:
    YEAR_BASE = 1990

    def __init__(self, dt: Optional[datetime] = None):
        self.dt = dt or datetime.now()

    def encode(self) -> bytes:
        year = self.dt.year - self.YEAR_BASE
        if not (0 <= year < 0x805):
            raise ACPComposeError("Invalid year")

        m, d, h, min_, s = self.dt.month, self.dt.day, self.dt.hour, self.dt.minute, self.dt.second

        b1 = (year << 2) | ((m >> 2) & 0x03)
        b2 = ((m & 0x03) << 6) | ((d << 1) & 0x3E) | ((h >> 4) & 0x01)
        b3 = ((h & 0x0F) << 4) | ((min_ >> 2) & 0x0F)
        b4 = ((min_ & 0x03) << 6) | (s & 0x3F)

        return _encode_ie(bytes([b1, b2, b3, b4]), ie_id=0)

class TimeSync:
    """TimeSync is used to sync time between TCU and server"""
    def __init__(self, dt: Optional[datetime] = None, flag: bool = False):
        self.dt = dt or datetime.now()
        self.flag = 1 if flag else 0

    def encode(self) -> bytes:
        year_offset = self.dt.year - Timestamp.YEAR_BASE
        if not (0 <= year_offset <= 0x3f) or self.dt.year >= 0x805:
            raise ACPComposeError("Invalid Year")
        if not (1 <= self.dt.month <= 12):
            raise ACPComposeError("Invalid Month")
        if not (1 <= self.dt.day <= 31):
            raise ACPComposeError("Invalid Day")
        if not (0 <= self.dt.hour <= 23):
            raise ACPComposeError("Invalid Hour")
        if not (0 <= self.dt.minute <= 59):
            raise ACPComposeError("Invalid Minutes")
        if not (0 <= self.dt.second <= 59):
            raise ACPComposeError("Invalid Seconds")


        b1 = (self.flag & 1) << 7

        month_hi = (self.dt.month >> 2) & 0x3
        month_lo = self.dt.month & 0x3
        b2 = ((year_offset & 0x3f) << 2) | month_hi

        hour_hi = (self.dt.hour >> 4) & 0x1
        hour_lo = self.dt.hour & 0xf
        b3 = (month_lo << 6) | ((self.dt.day & 0x1f) << 1) | hour_hi

        minutes_hi = (self.dt.minute >> 2) & 0xf
        minutes_lo = self.dt.minute & 0x3
        b4 = (hour_lo << 4) | minutes_hi

        b5 = (minutes_lo << 6) | (self.dt.second & 0x3f)

        # IE Type 0, More = 0, Length = 5
        return _encode_ie(bytes([b1, b2, b3, b4, b5]), ie_id=0)


class Auth:
    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password

    def encode(self) -> bytes:
        user_ie = _encode_ie(self.username, ie_id=1)
        pwd_ie = _encode_ie(self.password, ie_id=1)
        return _encode_ie(bytes(user_ie + pwd_ie), ie_id=0)


class EVCommandTail:
    def __init__(self, command_flag: bool = False, command: int = 0):
        self.command = command
        self.command_flag = command_flag

    def encode(self) -> bytes:
        if not (0 <= self.command <= 0x7f):
            raise ACPComposeError("Invalid command")
        b1 = ((int(self.command_flag) & 1) << 7) | (self.command & 0x7f)
        return _encode_ie(bytes([b1]), ie_id=0)

class HornRequest:
    def __init__(self, cmd_type: int, duration: int):
        # divide by 5, TCU multiplies by 5. input is seconds
        duration = duration/5
        if not (1 <= cmd_type <= 4):
            raise ACPComposeError(f"bad cmd_type={cmd_type}")
        if not (0 <= duration <= 0xF):
            raise ACPComposeError(f"bad duration={duration}")
        self.cmd_type = cmd_type
        self.duration = duration

    def encode(self) -> bytes:
        return _encode_ie(bytes(
            ((self.cmd_type & 0x7) << 5) | \
                  ((self.duration & 0xF) << 1)
        ), ie_id=0)

class EVTemperatureDummy:

    def encode(self) -> bytes:
        return _encode_ie(bytes([]), ie_id=0)