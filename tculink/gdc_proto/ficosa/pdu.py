import re
from typing import Tuple


def semi(num):
    n = b''
    for x in range(len(num) // 2):  # Use // for integer division in Python 3
        n += bytes([int(num[(x*2)+1]) << 4 | int(num[x*2])])
    if len(num) % 2 != 0:
        n += bytes([0xF0 | int(num[-1])])
    return n

def data_pdu(number: str, data: bytes|bytearray) -> Tuple[bytes, int]:
    """
    Generate Data PDU specifically for TCUs.

    number: international phone number without +
    data: binary data to add to PDU
    return: tuple (bytes, int), data and PDU length
    """
    number = re.sub('[^0-9]','', number)
    semi_num = semi(number)

    hdr = b''.join((
        b'\x00',  # SMSC info length, not included in PDU len
        b'\x11',  # First octet of SMS-SUBMIT message
        # 0x11 = message type SMS SUBMIT, validity
        # period present and relative
        b'\x00',  # Message reference
        len(number).to_bytes(1, 'big'),  # Length of the phone number (11)
        b'\x81',  # Type of number (0x81 = international)
        semi_num,  # Telephone number
        b'\x00',  # TP-PID Protocol ID.
        b'\x04',  # TP-DCS data coding scheme. 0x4=8 bit data
        b'\xAA',  # Validity period
        len(data).to_bytes(1, 'big'),  # TP-User-Data-Length. Length of the message
        data
    ))
    return hdr, len(hdr)