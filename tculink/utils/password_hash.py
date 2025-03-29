import re

def generate_crc32_table():
    table = []
    poly = 0xedb88320  # Reversed CRC-32 polynomial
    for i in range(256):
        value = i
        for _ in range(8):
            if value & 1:
                value = (value >> 1) ^ poly
            else:
                value = value >> 1
        table.append(value)
    return table


def crc32(data):
    """Compute the CRC-32 checksum of the input data."""
    data = data+b"evtelematics"
    crc_table = generate_crc32_table()
    crc = 0xffffffff

    for byte in data:
        crc = (crc >> 8) ^ crc_table[(crc & 0xff) ^ byte]

    return ~crc & 0xffffffff

def password_hash(password):
    crc_result = crc32(password.encode('ascii'))
    return "{:08x}".format(crc_result).upper()

def check_password_validity(input_str):
    if len(input_str) > 16:
        return False, "Password exceeds maximum length of 16 characters"

    pattern = r'^[A-Za-z0-9\-_=+@#?!]*$'

    if re.match(pattern, input_str):
        return True, "Password meets all requirements"
    else:
        return False, "Password contains characters not allowed in this password. Only letters, numbers and special characters - _ = + @ # ? ! are allowed"