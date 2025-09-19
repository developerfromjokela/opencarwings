from datetime import datetime

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
        payload += (0x8F if channel['enabled'] else 00).to_bytes(1, byteorder='big')
        payload += pad_bytes(channel['data1'])
        payload += pad_bytes(channel['data2'])
        payload += channel['flag2'].to_bytes(1, byteorder='big')
        payload += b'\x00'*5

    return payload

def create_cpinfo(obj):
    payload = bytearray(b'\xFF'*6)
    payload.extend(b'\x00'*3)
    payload.extend(b'\x01\x14')
    payload += obj['poi_id'].to_bytes(4, 'big')
    payload += len(obj['name']).to_bytes(1, 'big')
    payload += obj['name'].encode('utf-8')
    payload += len(obj['code']).to_bytes(1, 'big')
    payload += obj['code'].encode('utf-8')
    payload += len(obj['county']).to_bytes(1, 'big')
    payload += obj['county'].encode('utf-8')
    payload += len(obj['region']).to_bytes(1, 'big')
    payload += obj['region'].encode('utf-8')
    payload += len(obj['city']).to_bytes(1, 'big')
    payload += obj['city'].encode('utf-8')
    payload += len(obj['town']).to_bytes(1, 'big')
    payload += obj['town'].encode('utf-8')
    # usually meta1-3 empty, holiday or normal opening times?
    payload += len(obj['meta1']).to_bytes(1, 'big')
    payload += obj['meta1'].encode('utf-8')
    payload += len(obj['meta2']).to_bytes(1, 'big')
    payload += obj['meta2'].encode('utf-8')
    payload += len(obj['meta3']).to_bytes(1, 'big')
    payload += obj['meta3'].encode('utf-8')

    payload += construct_dms_coordinate(obj['lat'], obj['lon'])
    #payload += bytes.fromhex('80 00 0A 2D 06 C3 3B 36 11 00')
    payload += len(obj['address']).to_bytes(1, 'big')
    payload += obj['address'].encode('utf-8')
    payload += obj['mesh_id'].to_bytes(4, 'big')
    payload += len(obj['phone']).to_bytes(1, 'big')
    payload += obj['phone'].encode('utf-8')
    payload += len(obj['sites']).to_bytes(1, 'big')
    for site in obj['sites']:
        # 6-byte infoblock
        payload += site
    payload += len(obj['stations']).to_bytes(1, 'big')
    for station in obj['stations']:
        payload += b'\x00'*4
        # flag
        payload += station['flag1'].to_bytes(1, 'big')
        payload += station['fast_flag'].to_bytes(1, 'big')
        payload += station['slow_flag'].to_bytes(1, 'big')
        payload += station['flag2'].to_bytes(1, 'big')
        payload += b'\x00'*2
        payload += station['flag3'].to_bytes(1, 'big')
        # desc
        payload += len(station['opt_desc']).to_bytes(1, 'big')
        payload += station['opt_desc'].encode('utf-8')

    # config string for UI
    payload += len(obj['config_str']).to_bytes(2, 'big')
    payload += obj['config_str'].encode('utf-8')

    return payload

def build_autodj_payload(
    message_type: int,
    channel_id: int,
    adj_items: list,
    footer: dict,
    msg_id: int = 0x102,
    extra_fields: dict = None,
    header: bytes = b'\x00' * 7,
    skip_section: list = None
) -> bytes:
    """
    Builds binary data for the 0x102 message format using bytearray without struct.
    NOTE: Image resolution: 450 × 270, JPEG or PNG, preferably higher compression
    :param msg_id: The message ID (uint16).
    :param message_type: The flag1 value (0 or 1).
    :param channel_id: The channel ID (uint16).
    :param adj_items: List of dicts, each containing keys for ADJItem fields:
        - 'itemId': int (uint8)
        - 'itemFlag1': int (uint8)
        - 'dynamicDataField1': bytes (len <= 0x20)
        - 'dynamicDataField2': bytes (len <= 0x80)
        - 'dynamicDataField3': bytes (len <= 0x40)
        - 'DMSLocation': bytes (exactly 10 bytes)
        - 'flag2': int (uint8)
        - 'flag3': int (uint8)
        - 'dynamicField4': bytes (len <= 0x80)
        - 'dynamicField5': bytes (len <= 0x20)
        - 'dynamicField6': bytes (len <= 0x30)
        - 'unnamed_data': bytes (len <= 255, optional, default b'')
        - 'bigDynamicField7': bytes (len <= 0x400 recommended)
        - 'bigDynamicField8': bytes (len <= 0x400 recommended)
        - 'iconField': int (uint16)
        - 'longField2': int (uint16)
        - 'flag4': int (uint8)
        - 'unknownLongId4': int (uint32)
        - 'flag5': int (uint8)
        - 'flag6': int (uint8)
        - '12byteField1': bytes (exactly 12 bytes)
        - '12byteField2': bytes (exactly 12 bytes)
        - 'mapPointFlag': int (uint8)
        - 'flag8': int (uint8)
        - 'imageDataField': bytes (len <= 0x5000/20,480bytes/20.4kB)
    :param footer: Dict with 'type' (int) and 'data' depending on type:
        - type 2: 'data' bytes (exactly 9 bytes)
        - type 3 or 8: 'data' int (uint8)
        - type 4: {'len1': int (uint8), 'data2': bytes (len <= 255)}
        - type 6: 'data' bytes (len <= 255)
        - type 7: 'data' list of int (uint16, len <= 6)
        - type 10: {'a': int (uint8), 'b': int (uint8), 'data': bytes (len <= 255)}
    :param extra_fields: Dict for flag1-specific fields.
        - If flag1 == 0:
            - 'stringField1': bytes (<=0x20)
            - 'stringField2': bytes (<=0x80)
            - 'flag3': int (uint8)
            - 'unknownId': int (uint32)
            - 'field_len_0xc': bytes (exactly 12)
            - 'flag4': int (uint8)
            - 'countOfSomeItems': int (uint8, <=1)
            - 'mode0_processedFieldCntPos': int (uint8, <=6)
            - 'mode0_countOfSomeItems3': int (uint8, <=0x12)
        - If flag1 == 1:
            - 'countOfSomeItems': int (uint8, <=1)
    :param header: First 7 bytes of the body (default zeros).
    :param skip_section: List of 4-byte bytes objects (default empty).
    :return: The built binary body.
    """
    if extra_fields is None:
        extra_fields = {}
    if skip_section is None:
        skip_section = []

    # Validate adj_items count
    adj_count = len(adj_items)
    if adj_count > 6:
        raise ValueError("ADJItemsCount cannot exceed 6")

    # Build skip section
    n_skip = len(skip_section)
    if n_skip > 0xffff:
        raise ValueError("Skip section too large")
    skip_bytes = b''.join(skip_section)

    # Initialize body with header and skip section
    body = bytearray(header)
    body += n_skip.to_bytes(2, "big")
    body.extend(skip_bytes)

    # Start payload
    payload = bytearray()
    payload.extend(msg_id.to_bytes(2, "big"))
    payload += (message_type & 0xFF).to_bytes(1, "big")

    if message_type == 0:
        string_field1 = extra_fields.get('stringField1', b'')
        if len(string_field1) > 0x20:
            raise ValueError("stringField1 too long")
        string_field2 = extra_fields.get('stringField2', b'')
        if len(string_field2) > 0x80:
            raise ValueError("stringField2 too long")
        flag3 = extra_fields.get('flag3', 0)
        unknown_id = extra_fields.get('unknownId', 0)
        field_len_0xc = extra_fields.get('field_len_0xc', b'\x00' * 12)
        if len(field_len_0xc) != 12:
            raise ValueError("field_len_0xc must be 12 bytes")
        flag4 = extra_fields.get('flag4', 0)
        count_of_some_items = extra_fields.get('countOfSomeItems', 0)
        if count_of_some_items > 1:
            raise ValueError("countOfSomeItems <=1")
        mode0_processed_field_cnt_pos = extra_fields.get('mode0_processedFieldCntPos', 0)
        if mode0_processed_field_cnt_pos > 6:
            raise ValueError("mode0_processedFieldCntPos <=6")
        mode0_count_of_some_items3 = extra_fields.get('mode0_countOfSomeItems3', 0)
        if mode0_count_of_some_items3 > 0x12:
            raise ValueError("mode0_countOfSomeItems3 <=0x12")

        payload += channel_id.to_bytes(2, "big")
        payload += (len(string_field1) & 0xFF).to_bytes(1, "big")
        payload.extend(string_field1)
        payload += (len(string_field2) & 0xFF).to_bytes(1, "big")
        payload.extend(string_field2)
        payload += flag3.to_bytes(1, "big")
        payload += unknown_id.to_bytes(4, "big")
        payload.extend(field_len_0xc)
        payload += flag4.to_bytes(1, "big")
        payload += (adj_count & 0xFF).to_bytes(1, "big")
        payload += (count_of_some_items & 0xFF).to_bytes(1, "big")
        payload += (mode0_processed_field_cnt_pos & 0xFF).to_bytes(1, "big")
        payload += (mode0_count_of_some_items3 & 0xFF).to_bytes(1, "big")

    elif message_type == 1:
        count_of_some_items = extra_fields.get('countOfSomeItems', 0)
        if count_of_some_items > 1:
            raise ValueError("countOfSomeItems <=1")
        payload += channel_id.to_bytes(2, "big")
        payload += (adj_count & 0xFF).to_bytes(1, "big")
        payload += (count_of_some_items & 0xFF).to_bytes(1, "big")  # uint8

    else:
        raise ValueError("message_type must be 0 or 1")

    # Add AutoDJ items
    for item in adj_items:
        dynamic_data_field1 = item['dynamicDataField1']
        if len(dynamic_data_field1) > 0x20:
            raise ValueError("dynamicDataField1 too long")
        dynamic_data_field2 = item['dynamicDataField2']
        if len(dynamic_data_field2) > 0x80:
            raise ValueError("dynamicDataField2 too long")
        dynamic_data_field3 = item['dynamicDataField3']
        if len(dynamic_data_field3) > 0x40:
            raise ValueError("dynamicDataField3 too long")
        if len(item['DMSLocation']) != 10:
            raise ValueError("DMSLocation must be 10 bytes")
        dynamic_field4 = item['dynamicField4']
        if len(dynamic_field4) > 0x80:
            raise ValueError("dynamicField4 too long")
        dynamic_field5 = item['dynamicField5']
        if len(dynamic_field5) > 0x20:
            raise ValueError("dynamicField5 too long")
        dynamic_field6 = item['dynamicField6']
        if len(dynamic_field6) > 0x30:
            raise ValueError("dynamicField6 too long")
        unnamed_data = item.get('unnamed_data', b'')
        if len(unnamed_data) > 255:
            raise ValueError("unnamed_data too long")
        big_dynamic_field7 = item['bigDynamicField7']
        big_dynamic_field8 = item['bigDynamicField8']
        if len(item['12byteField1']) != 12:
            raise ValueError("12byteField1 must be 12 bytes")
        if len(item['12byteField2']) != 12:
            raise ValueError("12byteField2 must be 12 bytes")
        image_data_field = item['imageDataField']
        if len(image_data_field) > 0x5000:
            raise ValueError("imageDataField too long")

        payload += (item['itemId'] & 0xFF).to_bytes(1, "big")    # uint8
        payload.extend([0, 0])                   # skipped bytes
        payload += (item['itemFlag1'] & 0xFF).to_bytes(1, "big") # uint8
        payload += (len(dynamic_data_field1) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_data_field1)
        payload += (len(dynamic_data_field2) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_data_field2)
        payload += (len(dynamic_data_field3) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_data_field3)
        payload.extend(item['DMSLocation'])
        payload += (item['flag2'] & 0xFF).to_bytes(1, "big")
        payload += (item['flag3'] & 0xFF).to_bytes(1, "big")
        payload += (len(dynamic_field4) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_field4)
        payload += (len(dynamic_field5) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_field5)
        payload += (len(dynamic_field6) & 0xFF).to_bytes(1, "big")
        payload.extend(dynamic_field6)
        payload += (len(unnamed_data) & 0xFF).to_bytes(1, "big")
        payload.extend(unnamed_data)
        payload += b'\x00'
        payload += len(big_dynamic_field7).to_bytes(2, "big")
        payload.extend(big_dynamic_field7)
        payload += len(big_dynamic_field8).to_bytes(2, "big")
        payload.extend(big_dynamic_field8)
        payload += item['iconField'].to_bytes(2, "big")
        payload += item['longField2'].to_bytes(2, "big")
        payload.extend([0, 0])  # skipped bytes
        payload += item['flag4'].to_bytes(1, "big")
        payload += item['unknownLongId4'].to_bytes(4, "big")
        payload += item['flag5'].to_bytes(1, "big")
        payload += item['flag6'].to_bytes(1, "big")
        payload += (item['12byteField1'])
        payload += (item['12byteField2'])
        payload += item['mapPointFlag'] #bin
        payload += item['flag8'].to_bytes(1, "big")
        payload += len(image_data_field).to_bytes(4, "big")
        payload.extend(image_data_field)

    # Add footer
    ftype = footer['type']
    payload += ftype.to_bytes(1, "big")
    if ftype == 2:
        if len(footer['data']) != 10:
            raise ValueError("Footer type 2 data must be 10 bytes")
        payload.extend(footer['data'])
    elif ftype in (3, 8):
        payload += (footer['data'] & 0xFF).to_bytes(1, "big")  # uint8
    elif ftype == 4:
        len1 = footer['len1']
        data2 = footer['data2']
        len2 = len(data2)
        if len2 > 255:
            raise ValueError("Footer type 4 data2 too long")
        payload += (len1 & 0xFF).to_bytes(1, "big")  # uint8
        payload += (len2 & 0xFF).to_bytes(1, "big")  # uint8
        payload.extend(data2)
    elif ftype == 6:
        data = footer['data']
        l = len(data)
        if l > 255:
            raise ValueError("Footer type 6 data too long")
        payload += l.to_bytes(1, "big")
        payload.extend(data)
    elif ftype == 7:
        data = footer['data']
        count = len(data)
        if count > 6:
            raise ValueError("Footer type 7 count <=6")
        payload += (count & 0xFF).to_bytes(1, "big")  # uint8
        for u in data:
            payload += u.to_bytes(2, "big")
    elif ftype == 10:
        a = footer['a']
        b = footer['b']
        data = footer['data']
        l = len(data)
        if l > 255:
            raise ValueError("Footer type 10 data too long")
        payload += (a & 0xFF).to_bytes(1, "big")  # uint8
        payload += (b & 0xFF).to_bytes(1, "big")  # uint8
        payload += (l & 0xFF).to_bytes(1, "big")  # uint8
        payload.extend(data)
    else:
        raise ValueError("Unsupported footer type")

    body.extend(payload)
    return bytes(body)

def compose_ca_list(items):
    data = bytearray()
    data += b'\x00'*9
    data += b'\x01\x19'
    data += len(items).to_bytes(4, 'big')
    for item in items:
        data += item['poi_id'].to_bytes(4, 'big')
        data += construct_dms_coordinate(item['latitude'], item['longitude'])
    return data


def compose_ca_data(data_dict) -> bytes:
    """
    Compose CA Data in the format expected by Parse_CAData function.

    Parameters:
        data_dict: Dictionary containing the CA data fields

    Expected dictionary keys:
        - poi_id: int (default: 0)
        - charging_station_name: str (default: "")
        - char40_data: int (default: 0xFFFF)
        - dynamic_string2: str (default: "")
        - dynamic_string3: str (default: "")
        - dynamic_string4: str (default: "")
        - dynamic_string5: str (default: "")
        - skip_string1: str (default: "")
        - skip_string2: str (default: "")
        - latitude: poi latitude
        - longitude: poi longitude
        - dynamic_string6: str (default: "")
        - short_id1: int (default: 0)
        - short_id2: int (default: 0)
        - dynamic_string7: str (default: "")
        - conf_byte1: int (default: 0)
        - conf_byte2: int (default: 0)
        - station_type_id: int (default: 0)
        - station_type1_id: int (default: 0, only used if station_type_id == 1)
        - charge_station_items: list of dicts with 'mesh_point' and 'dynamic_field'
        - secondary_station_info: list of strings
        - third_station_info: list of strings
        - last_meta: list of meta object dicts

    Returns:
        bytes: The composed CA data
    """
    data = bytearray()

    data.extend(b'\x00' * 9)  # First 7 bytes (unknown purpose)

    # Message ID
    data.extend(b'\x01\x18')

    # POI_ID
    poi_id = data_dict.get('poi_id', 0)
    data += poi_id.to_bytes(4, 'big')

    # Charging station name (length byte + string)
    charging_station_name = data_dict.get('charging_station_name', '')
    name_bytes = charging_station_name.encode('utf-8')[:32]  # Max 32 chars
    data += (len(name_bytes).to_bytes(1, 'big'))
    data.extend(name_bytes)

    # char40 data (length byte + hex string representation)
    char40_bytes = data_dict.get('char40_data', '').encode('ascii')[:32]  # Max 32 chars
    data += (len(char40_bytes)).to_bytes(1, 'big')
    data.extend(char40_bytes)

    # Dynamic string 2 (length byte + string)
    dynamic_string2 = data_dict.get('dynamic_string2', '')
    str2_bytes = dynamic_string2.encode('utf-8')[:32]  # Max 32 chars
    data += (len(str2_bytes)).to_bytes(1, 'big')
    data.extend(str2_bytes)

    # Dynamic string 3 (length byte + string)
    dynamic_string3 = data_dict.get('dynamic_string3', '')
    str3_bytes = dynamic_string3.encode('utf-8')[:32]  # Max 32 chars
    data += (len(str3_bytes)).to_bytes(1, 'big')
    data.extend(str3_bytes)

    # Dynamic string 4 (length byte + string)
    dynamic_string4 = data_dict.get('dynamic_string4', '')
    str4_bytes = dynamic_string4.encode('utf-8')[:32]  # Max 32 chars
    data += (len(str4_bytes)).to_bytes(1, 'big')
    data.extend(str4_bytes)

    # Dynamic string 5 (length byte + string)
    dynamic_string5 = data_dict.get('dynamic_string5', '')
    str5_bytes = dynamic_string5.encode('utf-8')[:32]  # Max 32 chars
    data += (len(str5_bytes)).to_bytes(1, 'big')
    data.extend(str5_bytes)

    # Skip string 1 (length byte + string) - parser skips this
    skip_string1 = data_dict.get('skip_string1', '')
    skip1_bytes = skip_string1.encode('utf-8')[:32]
    data += (len(skip1_bytes)).to_bytes(1, 'big')
    data.extend(skip1_bytes)

    # Skip string 2 (length byte + string) - parser skips this
    skip_string2 = data_dict.get('skip_string2', '')
    skip2_bytes = skip_string2.encode('utf-8')[:32]
    data += (len(skip2_bytes)).to_bytes(1, 'big')
    data.extend(skip2_bytes)

    # String before mesh point (length byte + data + mesh point)
    mesh_str_len = 0  # We'll just use 0 for the string before mesh point
    data.append(mesh_str_len)

    # Mesh point data (10 bytes)
    data.extend(construct_dms_coordinate(data_dict.get('latitude', 0), data_dict.get('longitude', 0)))

    # Dynamic string 6 (length byte + string)
    dynamic_string6 = data_dict.get('dynamic_string6', '')
    str6_bytes = dynamic_string6.encode('utf-8')[:64]  # Max 64 chars
    data += (len(str6_bytes)).to_bytes(1, 'big')
    data.extend(str6_bytes)

    # Short IDs (2 bytes each, little endian)
    short_id1 = data_dict.get('short_id1', 0)
    short_id2 = data_dict.get('short_id2', 0)
    data += short_id1.to_bytes(2, 'big')
    data += short_id2.to_bytes(2, 'big')

    # Dynamic string 7 (length byte + string)
    dynamic_string7 = data_dict.get('dynamic_string7', '')
    str7_bytes = dynamic_string7.encode('utf-8')[:48]  # Max 48 chars
    data += (len(str7_bytes)).to_bytes(1, 'big')
    data.extend(str7_bytes)

    # Configuration bytes
    conf_byte1 = data_dict.get('conf_byte1', 0)
    conf_byte2 = data_dict.get('conf_byte2', 0)
    data.append(conf_byte1)
    data.append(conf_byte2)

    # Station type ID
    station_type_id = data_dict.get('station_type_id', 0)
    data.append(station_type_id)

    # Station type 1 ID (4 bytes) - only if station_type_id == 1
    if station_type_id == 1:
        station_type1_id = data_dict.get('station_type1_id', 0)
        data += station_type1_id.to_bytes(4, 'big')

    # Charge station items
    charge_station_items = data_dict.get('charge_station_items', [])
    if len(charge_station_items) > 5:
        raise ValueError("Maximum 5 charge station items allowed")

    data.append(len(charge_station_items))
    for item in charge_station_items:
        # Mesh point (10 bytes)
        data.extend(construct_dms_coordinate(item.get('lat', 0), item.get('lon', 0)))

        # Dynamic field (length byte + string)
        dyn_field = item.get('dynamic_field', '').encode('utf-8')[:32]
        data += (len(dyn_field)).to_bytes(1, 'big')
        data.extend(dyn_field)

    # Secondary station info
    secondary_station_info = data_dict.get('secondary_station_info', [])
    if len(secondary_station_info) > 5:
        raise ValueError("Maximum 5 secondary station info items allowed")

    data.append(len(secondary_station_info))
    for info in secondary_station_info:
        info_bytes = info.encode('utf-8')[:32]
        data += (len(info_bytes)).to_bytes(1, 'big')
        data.extend(info_bytes)

    # Third station info
    third_station_info = data_dict.get('third_station_info', [])
    if len(third_station_info) > 5:
        raise ValueError("Maximum 5 third station info items allowed")

    data.append(len(third_station_info))
    for info in third_station_info:
        info_bytes = info.encode('utf-8')[:32]
        data += (len(info_bytes)).to_bytes(1, 'big')
        data.extend(info_bytes)

    # Last meta data
    last_meta = data_dict.get('last_meta', [])
    if len(last_meta) > 32:
        raise ValueError("Maximum 32 last meta items allowed")

    data.append(len(last_meta))
    for i, meta in enumerate(last_meta):
        # Fast Charge method
        data.append(meta.get('fast_charge_method', 0))
        # Slow Charge Method
        data.append(meta.get('slow_charge_method', 0))
        # Flag 3
        data.append(meta.get('flag3', 0))
        # Unknown 2-byte value (little endian)
        unk_val = meta.get('unknown_short', 0)
        data += unk_val.to_bytes(2, 'big')

        # Big dynamic field (2 bytes length + data)
        big_field = meta.get('big_dynamic_field', b'')
        if len(big_field) > 1024:  # Max 0x400 bytes
            raise ValueError("big_dynamic_field must be <= 1024 bytes")
        data += len(big_field).to_bytes(2, 'big')
        data.extend(big_field)

        # Available status
        data.append(meta.get('avail_sts', 0))
        # Useable counter number
        data.append(meta.get('useable_cntr_num', 0))
        # Using counter number
        data.append(meta.get('using_cntr_num', 0))
        # Unknown counter number
        data.append(meta.get('unknown_cntr_num', 0))

        # Last updated date/time (7 bytes)
        # Format: 2 bytes year, then 5 bytes for month/day/hour/minute/second
        datetime_tstamp: datetime = meta.get('last_updated', None)
        if datetime_tstamp is None:
            raise ValueError("last_updated is invalid")
        data += datetime_tstamp.year.to_bytes(2, 'big')
        data += datetime_tstamp.month.to_bytes(1, 'big')
        data += datetime_tstamp.day.to_bytes(1, 'big')
        data += datetime_tstamp.hour.to_bytes(1, 'big')
        data += datetime_tstamp.minute.to_bytes(1, 'big')
        data += datetime_tstamp.second.to_bytes(1, 'big')

        # Supplier name (length byte + string)
        supplier = meta.get('supplier_name', '').encode('utf-8')[:64]
        data += (len(supplier)).to_bytes(1, 'big')
        data.extend(supplier)

        # Network name (length byte + string)
        network = meta.get('network_name', '').encode('utf-8')[:128]
        data += (len(network)).to_bytes(1, 'big')
        data.extend(network)

        # Reservation flag
        data.append(meta.get('reservation_flag', 0))

    return bytes(data)