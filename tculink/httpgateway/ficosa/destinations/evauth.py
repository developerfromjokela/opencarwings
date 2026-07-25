from db.models import Car
from tculink.gdc_proto.acp245 import composer
from tculink.gdc_proto.ficosa.utils import command_to_destination_id
import logging
logger = logging.getLogger("ficosa")

def handle(_, acp_data: dict, car: Car, source_id: int, __) -> bytes:
    """
    Checks for any pending actions and sends necessary data to execute the command.
    """

    dest_id = command_to_destination_id(car.command_type)
    if (not dest_id
            or not car.command_requested):
        logger.debug(f"Destination {dest_id} not authorized, details: {source_id}, {car.command_id}, {car.command_requested} {car.command_type}")
        # Acknowledge the command, but do not execute.
        # If ACK is not sent, the request will be repeated
        return b'ACK'

    acp_msg = bytearray()
    acp_msg += composer.VehDesc(vin=acp_data["veh_desc"]["vin"], dcm=acp_data["veh_desc"]["dcm"]).encode()
    acp_msg += dest_id.to_bytes(1, "little")  # dest ID
    acp_msg += acp_data.get("source_id", 0).to_bytes(1, "little")  # src ID

    if car.command_type == 1: # Battery info
        acp_msg += composer.EVCommandTail(command=1).encode()
        acp_msg += composer.TimeSync().encode()
    elif car.command_type == 2 or car.command_type == 6: # Charging
        acp_msg += composer.EVCommandTail(command=2).encode()
        acp_msg += composer.TimeSync().encode()
    elif dest_id == 0x2c: # A/C
        acp_msg += composer.EVCommandTail(
            command=(3 if car.command_type == 3 else 4)
        ).encode()

        if car.command_type == 3:
            acp_msg += composer.EVTemperatureDummy().encode()
        acp_msg += composer.TimeSync().encode()
    elif dest_id == 0x31: # Door Lock Unlock
        acp_msg += composer.EVCommandTail(command=6 if car.command_type == 7 else 5).encode()
        acp_msg += composer.TimeSync().encode()
    elif dest_id == 0x38: # Horn & Light
        ... # TODO
    else:
        car.command_result = 1
        car.save()
        return b'ACK'

    msg = bytearray()
    msg += composer.AppHeader(app_id=2, mcf=3, length=len(acp_msg), special_flag=1).encode()
    msg += acp_msg

    car.command_result = 3
    car.save()
    return bytes(msg)