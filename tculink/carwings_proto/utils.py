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