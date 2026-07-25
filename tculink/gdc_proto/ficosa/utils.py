
COMMAND_MAP = {
    1: 0x28,
    2: 0x2b,
    3: 0x2c,
    4: 0x2c,
    6: 0x3e,
    7: 0x31,
    8: 0x31,
    9: 0x38,
    10: 0x38
}

def command_to_destination_id(cmd: int) -> int|None:
    """
    Map OpenCARWINGS command ID to FICOSA TCU ACP Destination ID.
    """
    return COMMAND_MAP.get(cmd)