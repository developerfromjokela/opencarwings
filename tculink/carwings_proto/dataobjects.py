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