"""
Parse incoming GDC data packets
"""
from tculink.gdc_proto.datafields import get_packet_type, parse_tcu_info, parse_gps_info, get_body_type, parse_auth_info, parse_config_data, parse_evinfo


def parse_gdc_packet(byte_data):
    parsed_gps_data = None
    parsed_auth_data = None
    body_data = None

    if len(byte_data) < 5:
        raise Exception("Header data must be at least 5 bytes long")

    if len(byte_data) > 1024:
        raise Exception("Too much data for GDC packet")

    packet_type = get_packet_type(byte_data[0])
    if packet_type[0] == -1:
        raise Exception("Invalid packet type 0x{0:02x}", packet_type[0])

    if len(byte_data) < 100:
        raise Exception("Data must be at least 100 bytes long")

    body_type = get_body_type(byte_data[100])
    # Vehicle info
    tcu_info_data = byte_data[4:100]
    parsed_tcu_data = parse_tcu_info(tcu_info_data)

    if body_type != "config_read":
        if len(byte_data) < 153:
            raise Exception(f"Expected data packet length < 153 bytes for body type {body_type}")
        vehicle_env_data = byte_data[101:119]
        # Location
        location_data = vehicle_env_data[2:]
        parsed_gps_data = parse_gps_info(location_data)

        # Auth
        auth_data = byte_data[119:153]
        parsed_auth_data = parse_auth_info(auth_data)

        if packet_type[0] == 3:
            config_body = byte_data[153:]
            # AZE0 sends 0x92 as second byte, ZE0 sends 0x02, others unknown
            body_data = parse_evinfo(config_body, aze0=(byte_data[1] != 0x02))
    else:
        config_body = byte_data[102:]
        body_data = parse_config_data(config_body)


    return {
        "tcu": parsed_tcu_data,
        "gps": parsed_gps_data,
        "auth": parsed_auth_data,
        "message_type": packet_type,
        "body_type": body_type,
        "body": body_data
    }
