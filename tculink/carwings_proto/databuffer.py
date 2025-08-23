"""
Utility functions for parsing, de/compress and packing of CARWINGS packets
"""
import binascii
import zlib

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
    return result