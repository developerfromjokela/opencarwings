import hmac
import hashlib

# HMAC key hard-coded in 3G FICOSA / GMV Sistemas TCU
HMAC_KEY = bytes.fromhex("b8 8d dc e8 8e 64 ca 09 63 22 4e 2c 94 f3 10 10 3e 25 57 20 c0 4a 8f 79 4b 9f 9a 27 58 b6 00 b7")

def sms_acp_rn_hmac(data: bytes, key: bytes = HMAC_KEY) -> bytes:
    """
        Add "counter" element to ACP SMS data and generate HMAC of the message
        The counter is unchecked for Nissan TCUs
    """
    if len(data) < 1:
        raise Exception("Data is empty")

    hmac_data = bytearray(data)
    hmac_data += 0x01.to_bytes(4, "big") # counter set to 1

    # HMAC-SHA1
    mac = hmac.new(key, hmac_data, hashlib.sha1)
    hmac_data += mac.digest()
    return bytes(hmac_data)