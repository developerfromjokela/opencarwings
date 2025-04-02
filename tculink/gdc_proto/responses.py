import struct


def generate_tcu_key(dcm_id: str, iccid: str) -> bytes:
    """Generate a 20-byte TCU key from DCM ID and ICCID"""
    if len(dcm_id) < 10 or len(iccid) < 9:
        raise ValueError("DCM ID must be ≥ 10 bytes and ICCID must be > 9 bytes")

    # Take first 5 and last 5 bytes of each
    tcu_key = (
            dcm_id[:5] +  # First 5 of DCM ID
            iccid[:5] +  # First 5 of ICCID
            dcm_id[-5:] +  # Last 5 of DCM ID
            iccid[-5:]  # Last 5 of ICCID
    )
    return tcu_key.encode('ascii')


def create_packet_type_1() -> bytes:
    """Create a basic type 1 packet (no additional data)"""
    packet_type = 1  # Packet type 1
    protocol_ver = 2  # Protocol version?
    direction = 1  # Response
    size = 8  # Minimum size
    fixed_bytes = b'\x20\x5E\xB1\x70'  # Before auth bytes

    packet = struct.pack(
        '>BBBH4s',  # Big-endian: 1 byte, 1 byte, 1 byte, 2 bytes, 4 bytes
        packet_type,
        protocol_ver,
        direction,
        size,
        fixed_bytes
    )
    return packet

def create_config_read():
    return bytes.fromhex("040000082E000000")

def auth_common_dest():
    return bytes.fromhex("0200000827000080")

def conf_common_dest():
    return bytes.fromhex("0400000827000000")

def create_packet_type_3(body_type: int, auth_info: bytes = b'', body_data: bytes = b'') -> bytes:
    """Create a type 3 packet with additional data"""
    packet_type = 3  # Packet type 3
    protocol_ver = 2  # Protocol version?
    direction = 1  # Response
    fixed_bytes = b'\x20\x5E\xB1\x70'  # Before auth bytes

    # Calculate total size
    # Base size (8) + auth/info (75) + body type (1) + location (5) + auth len (1) + auth info + body
    auth_info_len = len(auth_info)
    base_size = 8 + 75 + 1 + 5 + 1
    total_size = base_size + auth_info_len + len(body_data)

    # Pad auth_info to minimum 35 bytes if shorter
    if auth_info_len < 35:
        auth_info = auth_info.ljust(35, b'\x00')
    auth_info_len = len(auth_info)

    packet = (
            struct.pack(
                '>BBBH4s',  # Base header
                packet_type,
                protocol_ver,
                direction,
                total_size,
                fixed_bytes
            ) +
            b'\x00' * 75 +  # Auth and info placeholder
            struct.pack('>B', body_type) +  # Body type
            b'\x00' * 5 +  # Potential location data
            struct.pack('>B', auth_info_len) +  # Auth info length
            auth_info +  # Auth information
            body_data  # Request body
    )
    return packet


def create_gdc_response(destination: int, command: int, success: bool = True) -> bytes:
    """Create a GDC Type 2 command response"""
    message_type = 2  # Authentication/Commands
    reserved = 0
    length = 8  # Fixed length for Type 2
    payload = 2  # Required by HandleRFCMessage
    reserved2 = 0

    # Command byte: MSB (0=success, 1=failure) + command code shifted left 4 bits
    msb = 0 if success else 1
    command_byte = (msb << 7) | (command << 4)

    packet = struct.pack(
        '>BBHBBBB',
        message_type,
        reserved,
        length,
        destination,
        payload,
        reserved2,
        command_byte
    )
    return packet


def create_charge_status_response(success: bool = True) -> bytes:
    """Create charge status response (destination 0x28, command 0x01)"""
    return create_gdc_response(0x28, 0x01, not success)


def create_charge_request_response(success: bool = True) -> bytes:
    """Create charge request response (destination 0x2B, command 0x02)"""
    return create_gdc_response(0x2B, 0x02, not success)


def create_ac_setting_response(success: bool = True) -> bytes:
    """Create AC setting response (destination 0x2C, command 0x03)"""
    return create_gdc_response(0x2C, 0x03, not success)


def create_ac_stop_response(success: bool = True) -> bytes:
    """Create AC stop response (destination 0x2C, command 0x04)"""
    return create_gdc_response(0x2C, 0x04, not success)
