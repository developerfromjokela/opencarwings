from db.models import Car


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