from db.models import Car
from django.utils.translation import gettext_lazy as _


def get_cws_authenticated_car(xml_data):
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
            if car.owner.username != username or car.owner.tcu_pass_hash != password:
                return None

            return car
        except Car.DoesNotExist:
            return None
    return None

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
    return LANG_CODES.get(lang, 'en')

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