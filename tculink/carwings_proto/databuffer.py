"""
Utility functions for parsing, de/compress and packing of CARWINGS packets
"""
import binascii
import zlib

# Lookup table for probe operations
PROBE_XOR_LOOKUPTABLE = [
    0xce, 0xf4, 0x46, 0xc2, 0x8e, 0xcb, 0x47, 0x82, 0x63, 0x48, 0x35, 0xa8, 0x94, 0x22, 0x00, 0x08,
    0x78, 0xbf, 0xe6, 0x43, 0x01, 0x87, 0x67, 0x7b, 0xdc, 0x53, 0x02, 0xaf, 0xd9, 0x93, 0x5a, 0x97,
    0x1e, 0x8b, 0x41, 0x15, 0x55, 0xd8, 0x9b, 0xbb, 0x49, 0x92, 0xab, 0x20, 0x28, 0x5b, 0x70, 0x51,
    0x6c, 0x1c, 0xa7, 0xb0, 0x50, 0xc3, 0x32, 0x4b, 0x3d, 0x1b, 0xbe, 0xe7, 0xae, 0xd0, 0xb7, 0x84,
    0xd7, 0xf9, 0xf6, 0xa1, 0x38, 0x27, 0xbd, 0xba, 0xa5, 0x62, 0x61, 0xeb, 0x5d, 0xec, 0x71, 0x2a,
    0x11, 0xd4, 0x05, 0xf1, 0xcf, 0xc5, 0x0b, 0x45, 0xfe, 0x9e, 0xca, 0x77, 0x68, 0xf2, 0x09, 0xad,
    0xf8, 0x3a, 0x3e, 0xef, 0x2e, 0x52, 0xb6, 0x83, 0x31, 0x96, 0x7a, 0x86, 0x33, 0x7c, 0x9a, 0xb2,
    0x0a, 0x88, 0xf5, 0x66, 0xcd, 0x18, 0x1d, 0x34, 0x10, 0xb3, 0xe5, 0x6a, 0x26, 0x7f, 0xf7, 0x7d,
    0x3f, 0x3c, 0x4e, 0x91, 0x58, 0xa6, 0xdd, 0x81, 0x21, 0x1a, 0x0c, 0xfa, 0x1f, 0xfb, 0xea, 0x5f,
    0x42, 0x79, 0x60, 0x39, 0x6d, 0xc1, 0x37, 0xa2, 0xa3, 0x16, 0x80, 0x99, 0xb9, 0xde, 0xa9, 0xee,
    0xdf, 0xb5, 0x74, 0x44, 0xd1, 0x6b, 0x57, 0xda, 0x72, 0xbc, 0x03, 0xd3, 0x8a, 0xc9, 0x75, 0x4a,
    0xe1, 0xa4, 0xed, 0xe4, 0xd5, 0x65, 0x12, 0x7e, 0xe3, 0x89, 0x9f, 0x29, 0xe2, 0xa0, 0x9c, 0x2f,
    0x85, 0x2b, 0xc4, 0x36, 0xe9, 0x59, 0x3b, 0x4f, 0xd2, 0x0f, 0xc0, 0xff, 0x40, 0xfd, 0x23, 0x56,
    0xc8, 0x2c, 0xb1, 0x17, 0x04, 0x4c, 0x8f, 0xe0, 0x07, 0x64, 0x06, 0x69, 0x6f, 0x9d, 0x73, 0x13,
    0x5c, 0x8c, 0x24, 0xe8, 0x2d, 0xfc, 0xd6, 0x5e, 0xac, 0x19, 0xdb, 0x0d, 0xf0, 0x54, 0xb8, 0x14,
    0x98, 0xf3, 0xc6, 0xb4, 0x6e, 0x0e, 0x95, 0x4d, 0x30, 0xcc, 0xaa, 0x90, 0xc7, 0x25, 0x8d, 0x76
]

def get_probe_xor_key(seed: int) -> int:
    """
    Derive the XOR key from the lookup table using provided seed (0-255).
    """
    if not 0 <= seed <= 255:
        raise ValueError("param_3 must be between 0 and 255")
    lower_nibble = seed & 0x0f
    upper_nibble = seed >> 4
    index = lower_nibble * 0x10 + upper_nibble
    return PROBE_XOR_LOOKUPTABLE[index]

def probe_xor_data(data: bytes, xor_seed: int) -> bytes:
    """
    Probe data 'encryption' (obfuscation)
    Perform the XOR operation on the entire data using the derived key from seed.
    """
    key = get_probe_xor_key(xor_seed)
    result = bytearray(data)
    for i in range(len(result)):
        result[i] ^= key
    return bytes(result)

def read_filename_and_size(byte_data, start_pos=0):
    result = bytearray()
    i = start_pos

    while i < len(byte_data) - 2:  # -2 because we check three bytes at a time
        if (byte_data[i] == 0 and
                byte_data[i + 1] == 0 and
                byte_data[i + 2] == 0):
            # Found three zeros, now read the next two bytes as size
            if i + 4 >= len(byte_data):  # Check if we have enough bytes left
                raise ValueError("Not enough bytes for size after triple zero")
            size = int.from_bytes(byte_data[i + 3:i + 5], byteorder='big')
            # Return content, size, and position after size bytes
            return bytes(result), size, i + 5
        result.append(byte_data[i])
        i += 1

    raise ValueError("No triple zero sequence found")

def parse_carwings_files(data):
    if len(data) < 8:
        raise ValueError("Data too short")

    print("- input data length", len(data))

    # header 8 bytes
    header = data[:8]
    body = data[8:]

    file_count = int.from_bytes(header[:4], "big")
    body_size = int.from_bytes(header[4:8], "big")

    print("- Files count", file_count)
    print("- Body size", body_size)

    if len(body) != body_size:
        raise ValueError("Body size mismatch! Expected %d bytes, got %d" % (body_size, len(body)))

    data = body[:body_size]

    filenames = {}
    complete_files = []

    offset = 0

    # Map out files
    for i in range(file_count):
        content1, size1, next_pos = read_filename_and_size(data, start_pos=offset)
        content1 = content1.decode("ascii")
        filenames[i] = (content1, size1)
        offset = next_pos

    for num, file in filenames.items():
        print("--- File", num, file)
        file_content = data[offset:offset + file[1]]
        offset += file[1]
        print("------- Length content:", len(file_content))
        complete_files.append({'name': file[0], 'size': file[1], 'content': file_content})

    return complete_files

def crc32_carwings(data):
    """Calculate CRC32 checksum."""
    crc = binascii.crc32(data) & 0xFFFFFFFF
    return crc.to_bytes(4, 'big')

def decompress_body(body):
   req_metadata = body[:8]

   decompressed_size = int.from_bytes(req_metadata[:4], 'big')

   compressed_size =  int.from_bytes(req_metadata[4:8], 'big')

   checksum = body[compressed_size+8:]
   calculated_checksum = crc32_carwings(body[:-4])
   if calculated_checksum != checksum:
       raise Exception("Checksum mismatch! Expected %s, got %s" % (checksum, calculated_checksum))

   zobj = zlib.decompressobj()
   comp_data = body[8:compressed_size+8]
   decomp_data = zobj.decompress(comp_data)

   if decompressed_size != len(decomp_data):
       raise Exception("Decompressed size mismatch!")

   return decomp_data


# Composing utils

def construct_carwings_filepacket(files):
    files_data = bytearray()
    for file in files:
        files_data += file[0].encode('ascii')
        files_data += b'\0'
        files_data += len(file[1]).to_bytes(4, 'big')

    for file in files:
        files_data += file[1]

    data_packet = bytearray()
    data_packet += (len(files).to_bytes(4, byteorder='big'))
    data_packet += (len(files_data).to_bytes(4, 'big'))
    data_packet += files_data
    return data_packet


def compress_carwings(binary_data, resume_id=b'\01'*20):
    compressed_packet_data = bytearray()

    compressed_packet_data += len(binary_data).to_bytes(4, byteorder='big')

    comp_data = zlib.compress(binary_data, 6)
    compressed_packet_data += len(comp_data).to_bytes(4, 'big')
    compressed_packet_data += comp_data

    # CRC32 checksum for data
    compressed_packet_data += crc32_carwings(compressed_packet_data)

    # Add resume_id field, low level metadata for subsequent data transfers in multiple parts
    resumed_compressed_packet_data = bytearray()
    resumed_compressed_packet_data += b'resume_id:'
    resumed_compressed_packet_data += resume_id
    resumed_compressed_packet_data += compressed_packet_data

    return resumed_compressed_packet_data


def get_carwings_bininfo(binary_data):
    if len(binary_data) < 6:
        return None
    if binary_data[0] != 0x01 or binary_data[1] != 0x20:
        return None
    pload_type = binary_data[2]
    result = bytearray()

    if pload_type != 0x01:
        end_marker = b'\x01\x0F'
        start_pos = 2
        end_pos = binary_data.find(end_marker, start_pos)
        if end_pos == -1:
            return result
        result.extend(binary_data[start_pos:end_pos])
    if pload_type == 0x01:
        return result[2:]
    return result