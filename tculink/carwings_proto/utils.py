from db.models import Car


def get_cws_authenticated_car(xml_data):
    if 'authentication' in xml_data['service_info']:

        car_vin = xml_data['service_info']['authentication']['vin']
        dcm_id = xml_data['service_info']['authentication']['dcm_id']
        sim_id = xml_data['service_info']['authentication']['sim_id']

        username = xml_data['service_info']['authentication']['user_id']
        password = xml_data['service_info']['authentication']['password']

        # find car
        try:
            car = Car(vin=car_vin)

            # confirm TCU ID
            if dcm_id != car.tcu_serial:
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