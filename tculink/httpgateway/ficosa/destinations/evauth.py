from db.models import Car
from tculink.gdc_proto.acp245 import composer
from tculink.gdc_proto.ficosa.utils import command_to_destination_id, CONFIGURATION_MAP, ConfigurationFieldType
import logging
logger = logging.getLogger("ficosa")

def handle(_, acp_data: dict, car: Car, source_id: int, __) -> bytes:
    """
    Checks for any pending actions and sends necessary data to execute the command.
    """

    if car.command_type == 15 and car.command_payload is not None:
        dest_id = CONFIGURATION_MAP[car.command_payload["config_type"]]["destination"]
    else:
        dest_id = command_to_destination_id(car.command_type)
    app_id = 2

    acp_msg = bytearray()
    acp_msg += composer.VehDesc(vin=acp_data["veh_desc"]["vin"], dcm=acp_data["veh_desc"]["dcm"]).encode()

    if (not dest_id
            or not car.command_requested or car.command_id != source_id):
        logger.warning(f"Destination {dest_id} not authorized, details: {source_id}, {car.command_id}, {car.command_requested} {car.command_type}")
        # return ACK with negative auth result
        app_id = 0x1d
        acp_msg += b'\x27'  # dest ID, auth
        acp_msg += source_id.to_bytes(1, "little")  # src ID
        acp_msg += composer.EVCommandTail(command=0).encode()
    elif car.command_type == 15 and car.command_payload is not None:
        app_id = 0x1f
        config_template = CONFIGURATION_MAP[car.command_payload["config_type"]]
        config_payload = car.command_payload
        acp_msg += dest_id.to_bytes(1, "little")
        acp_msg += source_id.to_bytes(1, "little")

        acp_msg += composer.EVCommandTail().encode()
        acp_msg += composer.TimeSync().encode()
        # service provisioning
        if dest_id == 0xf5:
            config_encoder = composer.ServiceProvisioning()
            # add services
            if config_payload["type"] == "send":
                config_payload = config_payload["data"]
                for field, info in config_template["fields"].items():
                    if field in config_payload:
                        value = config_payload[field]
                        field_type = info["type"]
                        service_id = info["info_id"]
                        if field_type == ConfigurationFieldType.PROVISIONING and value > 0:
                            config_encoder.add_entry(composer.ServiceProvisioningService(service_id, value == 2, 0))

            acp_msg += config_encoder.encode()
            logger.debug(f"<< ServProv Message: {acp_msg.hex()}")
        else:
            config_encoder = composer.ACPConfigEncoder()
            service_type = config_template["service_type"]
            # add data
            if config_payload["type"] == "send":
                config_payload = config_payload["data"]
                for field, info in config_template["fields"].items():
                    if field in config_payload:
                        value = config_payload[field]
                        field_type = info["type"]
                        if field_type == ConfigurationFieldType.NUMBER:
                            config_encoder.add_element(service_type, info["info_id"], value.to_bytes(info["length"], "little"))
                        elif field_type == ConfigurationFieldType.BOOLEAN:
                            config_encoder.add_element(service_type, info["info_id"], b"\x01" if value else b"\x00")
                        elif field_type == ConfigurationFieldType.ASCII or field_type == ConfigurationFieldType.UNICODE:
                            encoded_val = value.encode("ascii" if field_type == ConfigurationFieldType.ASCII else "utf-8")
                            if info.get("fill", False):
                                buf = bytearray(info["length"])
                                # doublecheck length
                                if len(encoded_val) > info["length"]:
                                    encoded_val = encoded_val[:info["length"]]
                                #insert to buffer
                                buf[:len(encoded_val)] = encoded_val
                                encoded_val = buf
                            config_encoder.add_element(service_type, info["info_id"], encoded_val)

            acp_msg += config_encoder.encode()
            logger.debug(f"<< Config ACP Message: {acp_msg.hex()}")
    else:
        acp_msg += dest_id.to_bytes(1, "little")  # dest ID
        acp_msg += source_id.to_bytes(1, "little")  # src ID
        car.command_result = 3

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
                # Check for A/C temp setting
                if car.command_payload is not None and "unit" in car.command_payload and "temp" in car.command_payload:
                    acp_msg += composer.EVTemperaturePayload(units=car.command_payload.get("unit", 0),
                                                             temp_val=car.command_payload.get("temp", 0)).encode()
                    car.command_payload = None
                else:
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
                acp_msg += composer.HornRequest(cmd_type=cmd_type, duration=20).encode()
        elif dest_id == 0x39:
            acp_msg += composer.EVCommandTail(command=0x10 if car.command_type == 13 else 0x11).encode()
            acp_msg += composer.TimeSync().encode()
            acp_msg += composer.RemoteStartRequest().encode()
        else:
            car.command_result = 1
            app_id = 0x1d
            acp_msg += dest_id.to_bytes(1, "little")  # dest ID
            acp_msg += source_id.to_bytes(1, "little")  # src ID
            acp_msg += composer.EVCommandTail(command=0).encode()
            acp_msg += composer.ServiceProvisioning().add_entry(composer.ServiceProvisioningService(0, 0, 0)).encode()

        car.save()

    msg = bytearray()
    msg += composer.AppHeader(app_id=app_id, mcf=3, length=len(acp_msg), special_flag=1).encode()
    msg += acp_msg

    return bytes(msg)