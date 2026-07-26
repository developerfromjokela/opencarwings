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

    acp_msg = bytearray()
    acp_msg += composer.VehDesc(vin=acp_data["veh_desc"]["vin"], dcm=acp_data["veh_desc"]["dcm"]).encode()

    if (not dest_id
            or not car.command_requested):
        logger.debug(f"Destination {dest_id} not authorized, details: {source_id}, {car.command_id}, {car.command_requested} {car.command_type}")
        # proceed with data refresh, no other commands allowed
        acp_msg += 0x28.to_bytes(1, "little")  # dest ID
        acp_msg += acp_data.get("source_id", 0).to_bytes(1, "little")  # src ID
        acp_msg += composer.EVCommandTail(command=1).encode()
        acp_msg += composer.TimeSync().encode()
    else:
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
            acp_msg += composer.EVCommandTail(command=0xe if car.command_type == 12 else 0xd).encode()
            acp_msg += composer.TimeSync().encode()
            if car.command_type == 12: # stop horn&light
                acp_msg += composer.HornRequest(cmd_type=4, duration=0).encode()
            else:
                # hard code duration 30 seconds for now
                cmd_type = 3
                if car.command_type == 9:
                    cmd_type = 2
                if car.command_type == 10:
                    cmd_type = 1
                acp_msg += composer.HornRequest(cmd_type=cmd_type, duration=5).encode()
        elif dest_id == 0x39:
            acp_msg += composer.EVCommandTail(command=0x10 if car.command_type == 13 else 0x11).encode()
            acp_msg += composer.TimeSync().encode()
            acp_msg += composer.RemoteStartRequest().encode()
        else:
            car.command_result = 1
            car.save()
            return b'ACK'

        car.command_result = 3
        car.save()

    msg = bytearray()
    msg += composer.AppHeader(app_id=2, mcf=3, length=len(acp_msg), special_flag=1).encode()
    msg += acp_msg

    return bytes(msg)