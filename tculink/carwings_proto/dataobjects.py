def pad_bytes(data: bytes, length=6, padding=b'\xFF') -> bytes:
    if len(data) > length:
        raise ValueError(f"Input data exceeds {length} bytes")
    return data + padding * (length - len(data))

def construct_fvtchn_payload(channels):
    payload = bytearray()
    payload.extend(b'\x00'*9)
    payload.extend(b'\x01\x05')

    payload.extend(len(channels).to_bytes(1, byteorder='big'))
    for channel in channels:
        payload += channel['position'].to_bytes(1, byteorder='big')
        payload += channel['id'].to_bytes(2, byteorder='big')
        payload += channel['channel_id'].to_bytes(2, byteorder='big')
        payload += len(channel['name1']).to_bytes(1, byteorder='big')
        payload += channel['name1'].encode('utf-8')
        payload += len(channel['name2']).to_bytes(1, byteorder='big')
        payload += channel['name2'].encode('utf-8')
        payload += channel['flag'].to_bytes(1, byteorder='big')

    return payload


def construct_dms_coordinate(latitude: float, longitude: float) -> bytearray:
    """
    Convert float latitude and longitude to a bytearray in DMS format.
    Format: [80 00] [lon_deg lon_min lon_sec*100] [lat_deg lat_min lat_sec*100]
    Each DMS component: 1 byte degrees, 1 byte minutes, 2 bytes seconds*100.
    Returns: bytearray of 10 bytes.
    """

    def to_dms(degrees_float: float) -> tuple[int, int, int]:
        degrees = int(abs(degrees_float))
        minutes_float = (abs(degrees_float) - degrees) * 60
        minutes = int(minutes_float)
        seconds = int((minutes_float - minutes) * 60 * 100)  # Seconds * 100
        return degrees, minutes, seconds

    # Convert latitude and longitude to DMS
    lat_deg, lat_min, lat_sec = to_dms(latitude)
    lon_deg, lon_min, lon_sec = to_dms(longitude)

    # Create bytearray
    result = bytearray(10)

    # Header: 80 00
    result[0] = 0x80
    result[1] = 0x00

    # Longitude: degrees, minutes, seconds*100 (2 bytes, big-endian)
    result[2] = lon_deg
    result[3] = lon_min
    result[4] = (lon_sec >> 8) & 0xFF  # High byte
    result[5] = lon_sec & 0xFF  # Low byte

    # Latitude: degrees, minutes, seconds*100 (2 bytes, big-endian)
    result[6] = lat_deg
    result[7] = lat_min
    result[8] = (lat_sec >> 8) & 0xFF  # High byte
    result[9] = lat_sec & 0xFF  # Low byte

    return result


def construct_chnmst_payload(folders, channels):
    payload = bytearray()
    payload.extend(b'\x00'*9)
    payload.extend(b'\x01\x01')

    payload.extend(len(folders).to_bytes(1, byteorder='big'))
    payload.extend(len(channels).to_bytes(2, byteorder='big'))

    for folder in folders:
        payload += folder['id'].to_bytes(2, byteorder='big')
        payload += folder['internal_id'].to_bytes(2, byteorder='big')
        payload += len(folder['name1']).to_bytes(1, byteorder='big')
        payload += folder['name1'].encode('utf-8')
        payload += len(folder['name2']).to_bytes(1, byteorder='big')
        payload += folder['name2'].encode('utf-8')
        payload += folder['icon'].to_bytes(2, byteorder='big')
        payload += folder['flag'].to_bytes(1, byteorder='big')

    for channel in channels:
        payload += channel['id'].to_bytes(2, byteorder='big')
        payload += channel['internal_id'].to_bytes(2, byteorder='big')
        payload += len(channel['name1']).to_bytes(1, byteorder='big')
        payload += channel['name1'].encode('utf-8')
        payload += len(channel['name2']).to_bytes(1, byteorder='big')
        payload += channel['name2'].encode('utf-8')
        payload += channel['folder_id'].to_bytes(2, byteorder='big')
        payload += channel['icon'].to_bytes(2, byteorder='big')
        payload += (0x80 if channel['enabled'] else 00).to_bytes(1, byteorder='big')
        payload += pad_bytes(channel['data1'])
        payload += pad_bytes(channel['data2'])
        payload += channel['flag2'].to_bytes(1, byteorder='big')
        payload += b'\x00'*5

    return payload


def construct_send_to_car_channel(destinations, channel_id = 0x000F):
    payload = bytearray()
    payload.extend(b'\x00'*9)
    payload.extend(b'\x01\x02')
    payload.extend(b'\x01')

    payload += channel_id.to_bytes(2, byteorder='big')
    payload += len(destinations).to_bytes(1, byteorder='big')
    payload += b'\x00'

    for idx, destination in enumerate(destinations):
        payload += idx.to_bytes(1, byteorder='big')
        payload += b'\x00\x00'
        payload += idx.to_bytes(1, byteorder='big')
        payload += len(destination['name']).to_bytes(1, byteorder='big')
        payload += destination['name'].encode('utf-8')
        payload += len(destination['name2']).to_bytes(1, byteorder='big')
        payload += destination['name2'].encode('utf-8')
        payload += len(destination['name3']).to_bytes(1, byteorder='big')
        payload += destination['name3'].encode('utf-8')
        # DMS coordinate
        payload += construct_dms_coordinate(destination['lat'], destination['lon'])
        payload += b'\x00\x00'
        payload += len(destination['name4']).to_bytes(1, byteorder='big')
        payload += destination['name4'].encode('utf-8')
        payload += len(destination['name5']).to_bytes(1, byteorder='big')
        payload += destination['name5'].encode('utf-8')
        payload += len(destination['name6']).to_bytes(1, byteorder='big')
        payload += destination['name6'].encode('utf-8')
        payload += b'\x00\x00'
        payload += len(destination['name7']).to_bytes(2, byteorder='big')
        payload += destination['name7'].encode('utf-8')
        payload += len(destination['name8']).to_bytes(2, byteorder='big')
        payload += destination['name8'].encode('utf-8')
        payload += destination['icon'].to_bytes(2, byteorder='big')
        payload.extend(b'\x00' * 36)

    return payload
