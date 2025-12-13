import logging
from django.utils import timezone

from carwings import settings
from db.models import Car
from django.utils.translation import gettext as _
from unidecode import unidecode
logger = logging.getLogger("carwings")


def get_cws_authenticated_car(xml_data, check_user=True) -> Car|None:
    if 'authentication' in xml_data:

        car_vin = xml_data['authentication']['vin']
        dcm_id = xml_data['authentication']['dcm_id']
        sim_id = xml_data['authentication']['sim_id']

        username = xml_data['authentication']['user_id']
        password = xml_data['authentication']['password']

        # find car
        try:
            car = Car.objects.get(vin=car_vin)

            # confirm TCU ID
            if dcm_id != car.tcu_model:
                return None

            # confirm SIM ID
            if car.iccid != sim_id:
                return None

            # confirm user&pass
            if check_user and (car.owner.username != username or car.owner.tcu_pass_hash != password):
                return None

            return car
        except Car.DoesNotExist:
            return None
    return None

def update_car_info(xml_data):
    car_obj = get_cws_authenticated_car(xml_data)
    if car_obj is not None:
        car_obj.last_connection = timezone.now()
        if 'base_info' in xml_data:
            if 'vehicle' in xml_data['base_info']:
                carrier = xml_data['base_info']['vehicle'].get('carrier')
                status = xml_data['base_info']['vehicle'].get('status', None)
                signal_level = xml_data['base_info']['vehicle'].get('rss', -1)
                odometer = xml_data['base_info']['vehicle'].get('odometer', -1)
                # odometer is not sent in every CarWings request
                if odometer is not None and odometer != -1:
                    car_obj.odometer = odometer
                if signal_level is None:
                    signal_level = -1
                if signal_level == "out":
                    signal_level = 0
                car_obj.signal_level = signal_level
                car_obj.carrier = carrier
                if status is not None:
                    car_obj.ev_info.car_running = True
                    car_obj.ev_info.car_gear = 0
                    if status == "run":
                        car_obj.ev_info.car_gear = 1
                    car_obj.ev_info.save()
                if 'coordinates' in xml_data['base_info']['vehicle']:
                    car_obj.coordinates = xml_data['base_info']['vehicle']['coordinates']
                    try:
                        car_coordinate = xml_coordinate_to_float(xml_data['base_info']['vehicle']['coordinates'])
                        car_obj.location.lat = car_coordinate[0]
                        car_obj.location.lon = car_coordinate[1]
                        car_obj.location.home = False
                        car_obj.location.save()
                    except Exception as e:
                        logger.exception(e)
            if 'software' in xml_data['base_info']:
                car_obj.navi_version = xml_data['base_info']['software'].get('navi', None)
                car_obj.map_version = xml_data['base_info']['software'].get('map', None)
                car_obj.tcu_version = xml_data['base_info']['software'].get('dcm', None)
        car_obj.save()


def calculate_prb_data_checksum(data, length):
    """
    Calculates checksum of data by summing bytes
    Args:
        data: A bytes-like object (e.g., bytes or bytearray) containing the input data.
        length: Integer specifying how many bytes to process (equivalent to uVar6 + 8).
    Returns:
        A single byte (int, 0-255) representing the sum of the first 'length' bytes modulo 256.
    """
    sum = 0
    if length > 1:
        for i in range(length - 1):
            if i < len(data):
                sum = (sum + data[i]) % 256
        length = 1  # Set length to 1 for the final byte
    if length == 1 and len(data) > 0:  # Process the final byte if length == 1
        sum = (sum + data[length - 1]) % 256
    return sum

def calculate_prb_update_checksum(data: bytes, length: int) -> int:
    if not data or length <= 0 or length > len(data):
        return 0

    checksum = 0
    if length > 1:
        # Sum the first length-1 bytes, modulo 256 to emulate char overflow
        for i in range(length - 1):
            checksum = (checksum + data[i]) & 0xFF

    return checksum

LANG_CODES = {
    "hun": "hu",
    "spa": "es",
    "slo": "sl",
    "cze": "cz",
    "pol": "pl",
    "grc": "gr",
    "nor": "no",
    "fin": "fi",
    "swe": "se",
    "dnk": "dk",
    "dut": "nl",
    "por": "pt",
    "ita": "it",
    "ger": "de",
    "fre": "fr",
    "uke": "en",
    "mex": "es",
    "caf": "en",
    "use": "en"
}

def carwings_lang_to_code(lang):
    return LANG_CODES.get(lang, settings.LANGUAGE_CODE)

def get_word_of_month_i18n(num):
    ordinal_dict = {
        1: _('first'), 2: _('second'), 3: _('third'), 4: _('fourth'), 5: _('fifth'),
        6: _('sixth'), 7: _('seventh'), 8: _('eighth'), 9: _('ninth'), 10: _('tenth'),
        11: _('eleventh'), 12: _('twelfth'), 13: _('thirteenth'), 14: _('fourteenth'), 15: _('fifteenth'),
        16: _('sixteenth'), 17: _('seventeenth'), 18: _('eighteenth'), 19: _('nineteenth'), 20: _('twentieth'),
        21: _('twenty-first'), 22: _('twenty-second'), 23: _('twenty-third'), 24: _('twenty-fourth'), 25: _('twenty-fifth'),
        26: _('twenty-sixth'), 27: _('twenty-seventh'), 28: _('twenty-eighth'), 29: _('twenty-ninth'), 30: _('thirtieth'),
        31: _('thirty-first')
    }
    return ordinal_dict.get(num, str(num))


def parse_std_location_precise(lat_int, lon_int):
    """
    Parse 32-bit latitude and longitude into GPS coordinates.
    """

    def dms_to_decimal(coord_int):
        degrees = (coord_int >> 24) & 0xFF
        minutes = (coord_int >> 16) & 0xFF
        seconds_x100 = coord_int & 0xFFFF
        seconds = seconds_x100 / 100.0
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        return decimal


    return dms_to_decimal(lat_int), dms_to_decimal(lon_int)

def parse_std_location(lat_int, lon_int):
    """
    Parse 32-bit latitude and longitude into GPS coordinates.
    """

    def to_decimal_degrees(coord_int):
        # Convert to decimal degrees: divide by 512 and then by 3600
        return (coord_int / 512.0) / 3600.0

    # Parse latitude and longitude
    lat_decimal = to_decimal_degrees(lat_int)
    lon_decimal = to_decimal_degrees(lon_int)

    return lat_decimal, lon_decimal


def xml_dms_to_decimal(dms):
    degrees, minutes, seconds = map(float, dms.split(','))
    return  degrees + (minutes / 60.0) + (seconds / 3600.0)

def xml_coordinate_to_float(crd):
    if crd.get('datum', '') != 'wgs84':
        raise Exception('Coordinate must be WGS84')
    return xml_dms_to_decimal(crd['latitude']), xml_dms_to_decimal(crd['longitude'])


def encode_utf8(text, limit=0):
    if not isinstance(text, str):
        text = str(text)

    result = bytearray()

    for char in text:
        code_point = ord(char)

        # Handle characters outside valid Unicode range (>= 0x110000)
        if code_point >= 0x110000:
            decoded_char = unidecode(char)
            if decoded_char:
                replacement_bytes = encode_utf8(decoded_char)
                if limit == 0 or len(result) + len(replacement_bytes) <= limit:
                    result.extend(replacement_bytes)
                continue
            else:
                raise ValueError(f"Character U+{code_point:X} exceeds valid Unicode range")

        # ascii
        if code_point < 0x80:
            if limit == 0 or len(result) + 1 <= limit:
                result.append(code_point)
        # 2-byte sequence
        elif code_point < 0x800:
            byte1 = 0xC0 | (code_point >> 6)
            byte2 = 0x80 | (code_point & 0x3F)

            # Validate first byte range (matches validation logic)
            if byte1 < 0xC2:
                raise ValueError(f"Invalid UTF-8 encoding for U+{code_point:X}")

            if limit == 0 or len(result) + 2 <= limit:
                result.append(byte1)
                result.append(byte2)
        # 3-byte sequence
        elif code_point < 0x10000:
            byte1 = 0xE0 | (code_point >> 12)
            byte2 = 0x80 | ((code_point >> 6) & 0x3F)
            byte3 = 0x80 | (code_point & 0x3F)

            if limit == 0 or len(result) + 3 <= limit:
                result.append(byte1)
                result.append(byte2)
                result.append(byte3)

        # 4-byte sequence
        elif code_point < 0x110000:
            byte1 = 0xF0 | (code_point >> 18)

            # Validate first byte doesn't exceed 0xF7
            if byte1 > 0xF7:
                ascii_replacement = unidecode(char)
                if ascii_replacement:
                    replacement_bytes = encode_utf8(ascii_replacement)
                    if limit == 0 or len(result) + len(replacement_bytes) <= limit:
                        result.extend(replacement_bytes)
                    continue
                else:
                    raise ValueError(f"Invalid UTF-8 encoding for U+{code_point:X}")

            byte2 = 0x80 | ((code_point >> 12) & 0x3F)
            byte3 = 0x80 | ((code_point >> 6) & 0x3F)
            byte4 = 0x80 | (code_point & 0x3F)

            if limit == 0 or len(result) + 4 <= limit:
                result.append(byte1)
                result.append(byte2)
                result.append(byte3)
                result.append(byte4)

    return bytes(result)